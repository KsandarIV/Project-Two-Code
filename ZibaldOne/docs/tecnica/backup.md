# Storia e backup (Mnemosyne)

Come funzionano le istantanee di ZibaldOne ([ADR-0006](../decisioni/ADR-0006-storia-e-backup-cifrati.md)). Il codice è in `src/zibaldone/storage/backups.py`, i comandi in `src/zibaldone/cli/backup_cmd.py`.

## Le istantanee
- Un'**istantanea** è una copia completa e coerente dei dati, come un commit di git. Si crea a mano (`zbone backup create`) o da sola, se il backup è automatico (di base): la copia di oggi nasce al primo momento utile dopo l'01:00, con l'app aperta.
- Ogni istantanea è un file in `backups/` dentro la cartella dati, con il nome dell'ora in UTC: `20261017T112233Z-a1b2c3.zbsnap`. Le ultime 6 cifre bastano per indicarla nei comandi.
- Dentro c'è uno zip con:
  - `manifest.json`: id, ora, versione dell'app, versione dello schema, motivo (manuale, automatica, prima di un ripristino, prima di un aggiornamento), nota, impronta SHA-256 e dimensione del database, numero di voci e modelli;
  - `zibaldone.db`: la copia fatta con l'API di backup di SQLite, coerente anche se l'app sta scrivendo;
  - `settings.json`: una copia delle impostazioni, per consultarla.
- Dalla 0.2.4 il manifest elenca anche gli **allegati** (`media`): i file stanno una volta sola accanto alle istantanee, come `<file>.zbblob`, cifrati come loro; verifica, ripristino, pulizia e Le Nuvole li trattano insieme alle istantanee ([gli allegati](allegati.md)).
- Prima che un aggiornamento dell'app cambi lo schema del database, ZibaldOne salva un'istantanea "prima di un aggiornamento".

## Ripristino
- `zbone backup restore ID` riporta modelli e voci com'erano. Prima controlla tutta l'istantanea, poi salva lo stato attuale come istantanea "prima di un ripristino", poi sostituisce il file in un colpo solo. Il comando stampa come annullare.
- Restano come sono adesso `settings.json` e `keys.json`: un'istantanea vecchia non deve revocare un consenso, cambiare la durata dei backup (cancellerebbe istantanee) o riportare una vecchia passphrase.
- ZibaldOne deve essere chiuso nelle altre finestre: un database in uso viene rilevato e il ripristino si ferma con un messaggio.

## Durata e modalità (dalla 0.3.1)
Due modalità, scelte in Mnemosyne o con `zbone backup config --auto/--manual`:
- **Automatico** (di base). Resta **la copia di oggi**, che ogni giorno sostituisce quella di ieri, più la copia **della settimana** (a 7 giorni, ne restano 4), **del mese** (a 28 giorni, 3) e **dell'anno** (a 365 giorni, 3): ogni nuova sostituisce la più vecchia del suo gruppo. Una voce cancellata può quindi restare nei backup fino a circa 3 anni, e l'avviso privacy (versione 6) lo dice.
- **Manuale**. Non nasce e non si cancella nulla da solo: le copie le fai e le cancelli tu.

Le copie fatte a mano e quelle «prima di un ripristino» non vengono mai tolte dall'app. Sulle destinazioni fuori dal dispositivo (Le Nuvole) si cancella solo ciò che il dispositivo ha già tolto. Al primo backup automatico dopo l'aggiornamento alla 0.3.1 le vecchie copie automatiche oltre l'ultima sono sostituite da questo schema.

```powershell
zbone backup config                                   # mostra la modalità
zbone backup config --manual                          # niente copie automatiche
zbone backup config --auto                            # torna all'automatico
zbone backup prune --dry-run                          # cosa cancellerebbe
```

## Il file di backup (`.zbbackup`, dalla 0.3.1)
Un solo file da portare via e riportare (`storage/bundle.py`): è uno zip senza compressione (dentro è già cifrato) con `bundle.json`, l'istantanea, i suoi allegati e, se la cifratura è attiva, `keys.json` con la chiave privata già chiusa da passphrase e codice di recupero. Da solo non apre nulla.
- App: Mnemosyne → «Salva in un file» e «Importa da un file». Terminale: `zbone backup export [--to CARTELLA|FILE]` (di base la cartella Download) e `zbone backup import FILE`.
- Importare non sovrascrive: aggiunge l'istantanea e gli allegati accanto agli altri e installa `keys.json` solo se il dispositivo non ne ha; i dati cambiano solo con il ripristino, dopo i soliti controlli.
- **Al primo avvio**: su un'installazione senza dati né backup propri, dopo il consenso, l'app cerca un `.zbbackup` in Download, Documenti e Scrivania e propone di riportarlo (passphrase o codice di recupero se è cifrato). Non blocca mai l'avvio.

## Verifica
`zbone backup verify` controlla l'ultima istantanea (`--all` tutte, oppure un ID): zip integro, impronta SHA-256, `PRAGMA integrity_check` di SQLite e versione dello schema.

## Cifratura · Anello di Gige (dalla 0.0.7)
Con `zbone backup setup` ogni istantanea viene cifrata sul dispositivo prima di essere scritta, e quelle già fatte vengono cifrate al loro posto. Il database sul dispositivo resta in chiaro: la cifratura riguarda le istantanee, cioè tutto ciò che può uscire dal dispositivo.

**Le chiavi.** Al setup l'app crea una coppia di chiavi X25519, salvata in `keys.json`:
- la **chiave pubblica** cifra ogni istantanea senza chiedere nulla: per questo i backup automatici non chiedono mai la passphrase;
- la **chiave privata**, che serve solo per verificare o ripristinare, è salvata solo protetta (AES-256-GCM) da più "serrature":
  - `passphrase`: scrypt della passphrase (n=2^15, r=8, p=1, con i parametri salvati accanto);
  - `recovery`: il **codice di recupero** mostrato una volta sola al setup;
  - `secret:<nome>`: un segreto di 32 byte; `secret:google` è il recupero con l'account Google (dalla 0.0.8, vedi sotto).

Cambiare passphrase cambia solo la sua serratura: le istantanee non vanno ricifrate. Passphrase, codice di recupero e chiave privata non vengono mai scritti su disco né nei log, e si chiedono sempre con un campo nascosto, mai da opzioni o variabili d'ambiente.

**Il file cifrato.** `ZBSEALED` + versione + intestazione JSON + nonce di 12 byte + testo cifrato AES-256-GCM. Ogni istantanea usa una chiave X25519 nuova (ECDH con la chiave pubblica dei backup, poi HKDF-SHA256). Tutto ciò che precede il testo cifrato è autenticato: un byte cambiato si scopre. L'intestazione in chiaro ripete solo id, ora, motivo e versioni; note e conteggi stanno nella parte cifrata. Contiene anche la serratura del codice di recupero, così **un solo file copiato altrove si apre con il codice di recupero**, anche senza `keys.json`.

**Il codice di recupero.** 7 gruppi di 4 caratteri, per esempio `XP8F-YBNT-EYHV-G6P0-HFV4-P8F8-1BKM`: 120 bit casuali più un gruppo di controllo, in base32 di Crockford. Gli errori di battitura si scoprono; maiuscole, spazi e trattini non contano, e O/0 e I/L/1 valgono uguale. Senza passphrase e senza codice di recupero le istantanee **non si possono aprire, da nessuno**.

```powershell
zbone backup setup        # passphrase, codice di recupero, cifra le istantanee esistenti
zbone backup passphrase   # cambia passphrase (serve quella attuale)
zbone backup recover      # nuova passphrase con il codice di recupero
zbone backup list --details   # chiede la passphrase e mostra note e contenuto
```

**Limiti noti.** Chi ha la chiave pubblica (non è segreta) potrebbe costruire un file che sembra un'istantanea valida: il ripristino controlla integrità e schema, non chi ha fatto il file. Python non può cancellare i segreti dalla memoria. Dopo aver cifrato le vecchie istantanee, i byte in chiaro possono restare sul disco finché non vengono sovrascritti. Non c'è ancora la rotazione della chiave né un nuovo codice di recupero.

## Copie fuori dal dispositivo · Le Nuvole (dalla 0.0.8)
Il codice è in `src/zibaldone/cloud/` ([ADR-0007](../decisioni/ADR-0007-account-google-e-destinazioni-cloud.md)).

**Destinazioni.** Per l'app una destinazione sa solo `list_files`, `upload`, `download` e `delete` di file con nomi semplici (`cloud/destinations.py`). Ce ne sono due:
- `LocalFolderDestination`: la sottocartella `ZibaldOne/` di una cartella scelta (chiavetta, OneDrive, Dropbox, Nextcloud…), con scritture atomiche;
- `GoogleDriveDestination`: lo spazio nascosto `appDataFolder` di Drive (API REST v3, caricamenti "resumable"). Con l'ambito `drive.appdata` l'app non vede nient'altro del Drive.

Aggiungere OneDrive o WebDAV vuol dire scrivere una classe in più, senza toccare il resto.

**Cosa esce.** Solo le istantanee cifrate (`*.zbsnap`), `keys.json` (chiave pubblica e chiave privata chiusa dalle serrature: senza passphrase, codice o segreto Google non serve) e, se attivo, `google-recovery.json`. Le istantanee in chiaro non escono mai: senza `zbone backup setup` la sincronizzazione si rifiuta.

**Sincronizzazione** (`cloud/sync.py`). `sync_now` carica le istantanee che mancano fuori (per nome e dimensione) e `keys.json`, poi applica fuori la stessa durata del dispositivo: tiene sempre ciò che il dispositivo ha ancora, cancella il resto solo se la durata non lo tiene. Non cancella mai una copia perché manca sul dispositivo: un telefono perso non deve portarsi via i suoi backup. Se fuori c'è il `keys.json` di un'altra chiave (un altro dispositivo con un altro setup), si ferma e lo dice. Dopo ogni backup automatico parte da sola (`maybe_sync`, che non fallisce mai: l'errore resta in `settings.json` e lo mostra `zbone cloud`).

**Recupero con l'account Google.** È facoltativo. `enable_google_recovery` crea un segreto casuale di 32 byte, lo mette in `google-recovery.json` sul Drive e aggiunge a `keys.json` la serratura `secret:google`. Su un dispositivo nuovo basta entrare con lo stesso account: l'app scarica chiavi e segreto e apre la chiave privata senza passphrase. Il compromesso è esplicito: chi entra nel tuo account Google può aprire i backup. `zbone cloud recovery off` toglie serratura e segreto.

**Un dispositivo nuovo.** `recover_from_cloud` scarica `keys.json` (se il dispositivo non ha chiavi), apre la chiave con passphrase, codice di recupero o segreto Google, scarica l'istantanea più recente (o quella scelta) e la ripristina come `zbone backup restore`.

**Token.** L'accesso usa OAuth 2.0 per app installate con PKCE e ritorno su `http://127.0.0.1:<porta>/` (`cloud/google_auth.py`). I token stanno in `account-token.json`: su Windows protetti con DPAPI (li legge solo lo stesso utente sullo stesso PC), altrove leggibili solo dall'utente. In `settings.json` ci sono solo email, nome e scelte.

## Export
`zbone export markdown` crea uno zip con un file Markdown per voce, da aprire in Obsidian; `zbone export csv` uno zip con un CSV per modello. Il codice è in `src/zibaldone/storage/export.py`. Gli export **non sono cifrati**: il comando lo ricorda.
