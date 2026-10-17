# Storia e backup (Mnemosyne)

Come funzionano le istantanee di ZibaldOne ([ADR-0006](../decisioni/ADR-0006-storia-e-backup-cifrati.md)). Il codice è in `src/zibaldone/storage/backups.py`, i comandi in `src/zibaldone/cli/backup_cmd.py`.

## Le istantanee
- Un'**istantanea** è una copia completa e coerente dei dati, come un commit di git. Si crea a mano (`zbone backup create`) o da sola una volta al giorno, dopo un comando che ha salvato qualcosa.
- Ogni istantanea è un file in `backups/` dentro la cartella dati, con il nome dell'ora in UTC: `20261017T112233Z-a1b2c3.zbsnap`. Le ultime 6 cifre bastano per indicarla nei comandi.
- Dentro c'è uno zip con:
  - `manifest.json`: id, ora, versione dell'app, versione dello schema, motivo (manuale, automatica, prima di un ripristino, prima di un aggiornamento), nota, impronta SHA-256 e dimensione del database, numero di voci e modelli;
  - `zibaldone.db`: la copia fatta con l'API di backup di SQLite, coerente anche se l'app sta scrivendo;
  - `settings.json`: una copia delle impostazioni, per consultarla.
- Prima che un aggiornamento dell'app cambi lo schema del database, ZibaldOne salva un'istantanea "prima di un aggiornamento".

## Ripristino
- `zbone backup restore ID` riporta modelli e voci com'erano. Prima controlla tutta l'istantanea, poi salva lo stato attuale come istantanea "prima di un ripristino", poi sostituisce il file in un colpo solo. Il comando stampa come annullare.
- Restano come sono adesso `settings.json` e `keys.json`: un'istantanea vecchia non deve revocare un consenso, cambiare la durata dei backup (cancellerebbe istantanee) o riportare una vecchia passphrase.
- ZibaldOne deve essere chiuso nelle altre finestre: un database in uso viene rilevato e il ripristino si ferma con un messaggio.

## Durata (retention)
Come `restic forget`: per ogni regola si tiene l'istantanea più recente di ognuno degli ultimi N giorni, settimane e mesi che ne hanno una. Di base **7 giornaliere, 4 settimanali, 12 mensili**: un dato cancellato può sopravvivere nei backup fino a circa 12 mesi, e l'avviso privacy lo dice. Si tengono sempre l'istantanea più recente e l'ultima "prima di un ripristino".

```powershell
zbone backup config                                   # mostra le impostazioni
zbone backup config --days 3 --weeks 2 --months 3     # durata più corta
zbone backup config --no-auto                         # niente istantanee automatiche
zbone backup config --interval 12                     # automatica ogni 12 ore
zbone backup prune --dry-run                          # cosa cancellerebbe
```

## Verifica
`zbone backup verify` controlla l'ultima istantanea (`--all` tutte, oppure un ID): zip integro, impronta SHA-256, `PRAGMA integrity_check` di SQLite e versione dello schema.

## Cifratura · Anello di Gige (dalla 0.0.7)
Con `zbone backup setup` ogni istantanea viene cifrata sul dispositivo prima di essere scritta, e quelle già fatte vengono cifrate al loro posto. Il database sul dispositivo resta in chiaro: la cifratura riguarda le istantanee, cioè tutto ciò che può uscire dal dispositivo.

**Le chiavi.** Al setup l'app crea una coppia di chiavi X25519, salvata in `keys.json`:
- la **chiave pubblica** cifra ogni istantanea senza chiedere nulla: per questo i backup automatici non chiedono mai la passphrase;
- la **chiave privata**, che serve solo per verificare o ripristinare, è salvata solo protetta (AES-256-GCM) da più "serrature":
  - `passphrase`: scrypt della passphrase (n=2^15, r=8, p=1, con i parametri salvati accanto);
  - `recovery`: il **codice di recupero** mostrato una volta sola al setup;
  - `secret:<nome>`: un segreto di 32 byte, usato dalla 0.0.8 per il recupero con l'account Google.

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

## Export
`zbone export markdown` crea uno zip con un file Markdown per voce, da aprire in Obsidian; `zbone export csv` uno zip con un CSV per modello. Il codice è in `src/zibaldone/storage/export.py`. Gli export **non sono cifrati**: il comando lo ricorda.
