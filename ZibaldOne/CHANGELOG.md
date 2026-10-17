# Changelog

Tutte le modifiche rilevanti di ZibaldOne. Formato ispirato a [Keep a Changelog](https://keepachangelog.com/it/1.1.0/), versioni [SemVer](https://semver.org/lang/it/).

## [Unreleased]

## [0.0.9] — 2026-10-17
### Aggiunto
- **Promemoria** (Daimon) per i 3 momenti della giornata: mattina 08:30, metà giornata 13:30, sera 21:30, con giorni della settimana e ore di silenzio (22:30–08:00).
- Al massimo un promemoria per momento al giorno, mai se la voce di quel momento è già scritta; un controllo in ritardo lo manda comunque una volta, dentro la sua finestra.
- Dopo 3 promemoria ignorati di fila, ZibaldOne propone di diradarli (`--thin-out`) o di lasciarli come sono (`--keep`).
- Messaggi brevi e gentili, che ruotano; la serie di giorni si festeggia e perderla non porta rimproveri. Le notifiche non contengono mai ciò che scrivi.
- `zbone remind status/config/fire/test`.
- `zbone remind install/uninstall` su Windows: attività pianificate, così i promemoria arrivano anche ad app chiusa.
- Notifiche di sistema con il pacchetto facoltativo `zibaldone[notifiche]` (desktop-notifier); senza, il promemoria compare nel terminale.
### Cambiato
- Avviso privacy versione 4: le notifiche si vedono a schermo bloccato. Chi aveva accettato lo rivede una volta.
- Roadmap: le notifiche passano prima dell'interfaccia, che le usa. Interfaccia grafica ora 0.1.0, prima versione per i tester 0.1.1.
### Corretto
- Pacchetto Stoa · Diario 1.0.1: "Voto alla settimana" e "Obiettivi per la prossima settimana" (prima "al settimana", "il prossimo settimana"). Per aggiornarli: `zbone pack install diario`.
### Documentazione
- Guida rapida con i promemoria; ADR-0008 con le scelte fatte.

## [0.0.8] — 2026-10-17
### Aggiunto
- **Account e copie fuori** (Le Nuvole): `zbone account login/logout` con Google (OAuth per app desktop, PKCE, ritorno su 127.0.0.1) e `zbone account` per vedere chi sei.
- Al primo avvio l'accesso con Google è obbligatorio per usare il diario, quando l'app ha un client Google configurato; senza client resta tutto locale. Backup, export e privacy non chiedono mai l'accesso.
- Tre modalità: `zbone cloud use local`, `google` (spazio nascosto dell'app su Drive, ambito `drive.appdata`) o `folder PERCORSO` (chiavetta, OneDrive, Dropbox…).
- Dopo ogni backup automatico (e dopo `backup create`, `setup`, `passphrase`, `recover`) le istantanee cifrate nuove vengono copiate sulla destinazione, con la stessa durata del dispositivo. Le istantanee in chiaro non escono mai.
- `zbone cloud`, `cloud sync`, `cloud list`, `cloud forget`.
- **Dispositivo nuovo**: `zbone cloud recover [ID]` riporta i dati con passphrase, codice di recupero (`--code`) o account Google.
- **Recupero con l'account Google**, facoltativo: `zbone cloud recovery on/off`, proposto quando scegli Drive, con il compromesso spiegato.
- Token Google in `account-token.json`, protetti con DPAPI su Windows; mai in `settings.json`.
### Cambiato
- Avviso privacy versione 3: account Google e copie su Drive. Chi aveva accettato lo rivede una volta.
### Documentazione
- [Creare il client OAuth di Google](docs/sviluppo/google-cloud.md), passo passo e gratis in modalità test.
- [Copie fuori dal dispositivo](docs/tecnica/backup.md#copie-fuori-dal-dispositivo--le-nuvole-dalla-008); guida rapida con Le Nuvole; ADR-0007 con le scelte fatte.

## [0.0.7] — 2026-10-17
### Aggiunto
- **Cifratura dei backup** (Anello di Gige): `zbone backup setup` con passphrase e codice di recupero; da lì ogni istantanea è cifrata (X25519 + AES-256-GCM) e quelle già fatte vengono cifrate al loro posto.
- I backup automatici non chiedono la passphrase: cifrano con la chiave pubblica.
- `zbone backup passphrase` (cambia passphrase) e `zbone backup recover` (nuova passphrase con il codice di recupero).
- `zbone backup list --details` mostra note e contenuto delle istantanee cifrate, dopo la passphrase.
- Un'istantanea cifrata copiata altrove si apre con il solo codice di recupero, anche senza `keys.json`.
### Cambiato
- L'avviso privacy dice che il database resta in chiaro e che i backup si cifrano con `zbone backup setup`. È un rischio che si riduce, quindi non serve accettarlo di nuovo.
### Documentazione
- [Cifratura](docs/tecnica/backup.md#cifratura--anello-di-gige-dalla-007): chiavi, formato dei file, codice di recupero, limiti noti; ADR-0006 aggiornato.

## [0.0.6] — 2026-10-17
### Aggiunto
- **Storia e backup** (Mnemosyne): istantanee complete dei dati come commit, in `backups/` nella cartella dati.
- Un'istantanea automatica al giorno, dopo il primo comando che salva qualcosa, e una prima di ogni aggiornamento del database. Se non riesce, un avviso giallo; il comando che hai lanciato non fallisce.
- `zbone backup create/list/restore/verify/prune/config`. Il ripristino salva prima lo stato attuale, così si può annullare.
- Durata a tempo come restic: di base 7 giornaliere, 4 settimanali, 12 mensili.
- Verifica: impronta SHA-256, integrità di SQLite, versione dello schema.
- `zbone export markdown` (un file per voce, per Obsidian) e `zbone export csv` (un foglio per modello), dentro uno zip.
- Il motore di cifratura è già nel codice (`core/crypto.py`, `storage/keys.py`) ma si attiva con i comandi della 0.0.7.
### Cambiato
- **Nuova numerazione** ([ADR-0010](docs/decisioni/ADR-0010-numerazione-delle-versioni.md)): tutto scende di un livello (0.N → 0.0.N, 1.N → 0.1.N, "v2" → 0.2) e la 1.0 è l'app davvero usabile. Commit, tag e note delle versioni già fatte sono stati rinumerati.
- Avviso privacy versione 2: dice che le istantanee conservano anche le voci cancellate finché non scadono. Chi aveva accettato lo rivede una volta.
- Nuova dipendenza: `cryptography`.
### Corretto
- Nella guida rapida mancava il titolo della sezione sul pensiero del giorno.
### Documentazione
- [Storia e backup](docs/tecnica/backup.md); guida rapida con backup ed export; roadmap con la [strada verso la 1.0](docs/tecnica/roadmap.md#verso-la-10).

## [0.0.5] — 2026-10-17
### Aggiunto
- `zbone pack export`: salva uno o più modelli in un file `.zbpack.json` da condividere, con nome, autore, versione e licenza. Contiene solo la struttura, mai le voci.
- `zbone pack import`: installa un pacchetto ricevuto, con lo stesso piano e la stessa conferma di `pack install`.
- File di pacchetto controllati prima di tutto: massimo 1 MB, formato 1, campi conosciuti, blocchi esistenti.
- `scripts/version_watch.py`: resta acceso e, quando cambia `__version__`, aggiorna CHANGELOG e nota, fa commit e tag da solo. Il push si attiva con `--push`.
### Documentazione
- [Versionamento automatico](docs/sviluppo/versionamento.md): il watcher, il rilascio a mano, le regole.
- [Guida rapida](docs/utente/guida-rapida.md): condividere i modelli.

## [0.0.4] — 2026-10-17
### Aggiunto
- **Pacchetti integrati** con nomi di scuole filosofiche: `diario` (Stoa, 8 modelli), `collezioni` (Museion, 9), `io` (Delfi, 5), `persone` (Agorà, 2). Riprendono le idee della vecchia Journal App come modelli modificabili.
- `zbone pack list`, `zbone pack show`, `zbone pack install`: prima di installare mostra cosa cambierà (nuovo, aggiornato, già presente, copia) e chiede conferma.
- Un modello dell'utente con lo stesso nome tecnico non viene mai sovrascritto: il pacchetto lo installa come copia.
- Ogni modello installato ricorda da quale pacchetto e versione viene.
- **Identità**: nomi filosofici per blocchi, modelli e parti dell'app (per esempio "Aut-Aut · Scelta"), 8 mascotte, una per area della vita, più una proposta per l'app.
- `zbone pensiero` (una frase di un filosofo al giorno, con la fonte) e `zbone about`.
- Dopo il consenso l'app suggerisce `zbone pack install diario`.
### Documentazione
- [Identità](docs/brand/identita.md): nome, tono, nomi filosofici con le fonti, mascotte.
- [Guida rapida](docs/utente/guida-rapida.md) con i modelli pronti.

## [0.0.3] — 2026-10-17
### Aggiunto
- **Blocchi**: 12 tipi con regole e messaggi in italiano: `text`, `longtext`, `number`, `rating`, `tags`, `date`, `checklist`, `scale`, `choice`, `progress`, `bookmark`, `link`. Quelli previsti per la v0.0.4 sono arrivati già qui.
- **Modelli** (`BlockSpec`, `Template`) e **voci** (`Entry`) che si trasformano in JSON e ritorno senza perdere nulla e rifiutano i campi sconosciuti.
- Database SQLite `zibaldone.db` nella cartella dati, con migrazioni che si possono solo aggiungere (`PRAGMA user_version`).
- `zbone template create/list/show/delete/blocks`: modelli con le domande, in una riga (`--block`, `--option`) o da file JSON.
- `zbone entry add/list/show/edit/delete`: voci con le domande o con `--set`, filtri per modello e giorno, id abbreviati, collegamenti per titolo.
- Date scritte come `2026-10-17`, `17/10/2026`, `oggi`, `ieri`.
- `scripts/release.py`: rilascio di una versione (test, CHANGELOG, nota, commit e tag `zibaldone-vX.Y.Z`).
- La versione si scrive in un solo posto, `src/zibaldone/__init__.py`; `pyproject.toml` la legge da lì.
### Documentazione
- Requisiti di privacy, sicurezza e conformità ([ADR-0002](docs/decisioni/ADR-0002-local-first-e-privacy.md)).
- Piano di distribuzione e aggiornamenti per i tester ([ADR-0003](docs/decisioni/ADR-0003-distribuzione-e-aggiornamenti.md)).
- Interfaccia con Flet e dati in SQLite ([ADR-0004](docs/decisioni/ADR-0004-flet-e-sqlite.md)).
- Pacchetti di modelli condivisibili tra utenti, modelli pronti e futuri consigli nello stesso formato ([ADR-0005](docs/decisioni/ADR-0005-pacchetti-di-modelli.md)); roadmap aggiornata.
- Storia dei dati e backup cifrati a tempo, anche fuori dal dispositivo e leggibili solo dall'utente ([ADR-0006](docs/decisioni/ADR-0006-storia-e-backup-cifrati.md)).
- Accesso con Google obbligatorio, scelta tra solo locale e locale + Google Drive, destinazioni cloud intercambiabili ([ADR-0007](docs/decisioni/ADR-0007-account-google-e-destinazioni-cloud.md)).
- Setup Windows/PowerShell; parti IA rinviate.
- [Visione](docs/tecnica/visione.md): tutto in uno a moduli (diario, collezioni, documenti, finanze, password via Bitwarden, grafo, raccomandazioni), Windows + Android + Linux futuro, sincronizzazione PC ↔ telefono.
- [Roadmap fino alla v0.1.5](docs/tecnica/roadmap.md) e [confronto con la vecchia Journal App](docs/tecnica/confronto-journal-app.md).
- Notifiche che spronano a scrivere ([ADR-0008](docs/decisioni/ADR-0008-notifiche.md)) e anonimizzatore per i futuri modelli di IA ([ADR-0009](docs/decisioni/ADR-0009-anonimizzatore.md)).
- [Requisiti dello sprint v0.2](docs/tecnica/requisiti-v0.2.md) dai documenti della vecchia Journal App (8 aree).
- [Guida rapida](docs/utente/guida-rapida.md) con modelli e voci; [riferimento dei blocchi](docs/tecnica/blocchi.md); dati e migrazioni in [architettura](docs/tecnica/architettura.md).

## [0.0.2] — 2026-10-17
### Aggiunto
- Cartella dati per piattaforma (`%APPDATA%\ZibaldOne` su Windows), sostituibile con la variabile `ZIBALDONE_HOME`.
- Avviso privacy al primo avvio con consenso esplicito (sì/no); se rifiuti non viene salvato nulla.
- `zbone privacy`: avviso, cartella, spazio usato e stato del consenso. `zbone privacy accept` e `zbone privacy revoke`.
- `zbone data path`: stampa il percorso della cartella dati.
- `settings.json` con `schema_version`, scritto in modo atomico.
- Test della privacy e del salvataggio, sempre in una cartella temporanea.

## [0.0.1] — 2026-10-17
### Aggiunto
- Scheletro del progetto: pacchetto `zibaldone` in `src/`, `pyproject.toml`.
- CLI con due nomi: `zibaldone` e l'alias corto `zbone`.
- Comandi `help` (elenca tutti i comandi) e `version`.
- Test della CLI con pytest.
- Struttura `docs/` con guida utente, architettura, decisioni, note di versione e setup su Windows.
