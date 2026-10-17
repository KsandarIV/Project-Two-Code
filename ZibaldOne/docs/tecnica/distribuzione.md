# Distribuzione e aggiornamenti

Obiettivo: far provare ZibaldOne agli amici, che useranno **smartphone Android**, e mandare **patch** senza rifare tutto a mano.

## Piattaforme
| Dove | Come | Chi |
|---|---|---|
| **Android** | app installabile (APK) | tester |
| **Windows** | CLI `zibaldone` / `zbone` da PowerShell, poi interfaccia grafica | Alex e chi usa il PC |

Scelta tecnica ([ADR-0004](../decisioni/ADR-0004-flet-e-sqlite.md)): **un solo codice Python** per il cuore dell'app (`core/`, `storage/`) e un'interfaccia con **Flet**, che produce sia l'app Windows sia l'APK Android dallo stesso codice. La CLI resta un'interfaccia in più sopra lo stesso cuore.

## Versioni
- **SemVer**: `MAJOR.MINOR.PATCH`. Una correzione è una *patch* (`0.3.0` → `0.3.1`), una funzione nuova è una *minor* (`0.3.1` → `0.4.0`).
- Ogni versione ha un tag git, una voce nel CHANGELOG e una nota in `docs/versioni/`.

## Canale per i tester Android
1. **Fase 1 — APK su GitHub Releases**: ogni tag produce un APK allegato alla release. I tester lo installano consentendo "app da origini sconosciute". All'avvio l'app controlla se c'è una versione nuova e lo dice.
2. **Fase 2 — Google Play, test interno**: aggiornamenti automatici dal Play Store per un gruppo chiuso di tester. Richiede un account sviluppatore Google (costo una tantum) e la policy sulla privacy pubblicata.

## Dati e aggiornamenti
- Ogni archivio dati porta uno `schema_version`. Un aggiornamento che cambia il formato include una **migrazione** automatica, con backup prima di applicarla.
- Un aggiornamento non deve mai cancellare i dati dell'utente. Su Android i dati restano nella memoria privata dell'app: disinstallare l'app li cancella, va detto ai tester insieme all'export.
