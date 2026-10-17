# Roadmap

Ogni versione aggiunge **una sola** capacità. Piattaforme: **Android** (tester) e **Windows** (CLI e desktop). Interfaccia con **Flet** e dati in **SQLite** ([ADR-0004](../decisioni/ADR-0004-flet-e-sqlite.md)). Le funzioni IA sono rinviate.

| Versione | Capacità | Stato |
|---|---|---|
| v0.0.1 | Scheletro: `help`, `version`, docs, test, CHANGELOG | ✅ |
| v0.0.2 | **Cartella dati e trasparenza**: primo avvio con avviso e consenso, `zbone privacy` (dove sono i dati, quanto pesano, rischi), `zbone data path` | ✅ |
| v0.0.3 | Modelli e voci con 4 blocchi base (text, number, rating, tags); modelli descritti in modo dichiarativo e serializzabile | ⬜ |
| v0.0.4 | Altri blocchi (slider, checklist, bookmark, date, progress) e modelli pronti forniti dall'app come pacchetti integrati | ⬜ |
| v0.0.5 | **Pacchetti di modelli condivisibili**: `zbone pack export/import/list/show`, anteprima e controlli all'import ([ADR-0005](../decisioni/ADR-0005-pacchetti-di-modelli.md)) | ⬜ |
| v0.0.6 | **Storia e backup**: istantanee locali come commit, `zbone backup create/list/restore/prune`, conservazione a tempo, export Markdown ([ADR-0006](../decisioni/ADR-0006-storia-e-backup-cifrati.md)) | ⬜ |
| v0.0.7 | **Cifratura e cloud**: passphrase e codice di recupero, backup sempre cifrati; accesso con Google obbligatorio, scelta tra solo locale e locale + Google Drive ([ADR-0007](../decisioni/ADR-0007-account-google-e-destinazioni-cloud.md)) | ⬜ |
| v0.0.8 | Prima interfaccia grafica, su Windows e Android dallo stesso codice | ⬜ |
| v0.0.9 | Distribuzione ai tester: APK su GitHub Releases, controllo aggiornamenti, migrazioni dei dati | ⬜ |
| futuro | Sincronizzazione PC ↔ telefono; collegamenti e **grafo** stile Obsidian; moduli Documenti, Finanze, Password (Bitwarden); Linux; altri cloud configurabili dall'utente (OneDrive, Dropbox, Nextcloud); pacchetti via link o QR e catalogo della comunità | ⬜ |
| futuro (IA) | Raccomandazioni basate su letture e riflessioni, configurazioni di blocchi consigliate, trascrizione, emozioni, blocco ISBN | ⬜ |

Moduli e principi: [visione](visione.md).
