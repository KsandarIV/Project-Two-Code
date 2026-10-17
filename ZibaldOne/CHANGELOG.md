# Changelog

Tutte le modifiche rilevanti di ZibaldOne. Formato ispirato a [Keep a Changelog](https://keepachangelog.com/it/1.1.0/), versioni [SemVer](https://semver.org/lang/it/).

## [Unreleased]

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
