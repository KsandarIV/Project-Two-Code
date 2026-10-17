# Distribuzione e aggiornamenti

Obiettivo: far provare ZibaldOne agli amici, che useranno **smartphone Android**, e mandare **patch** senza rifare tutto a mano.

## Piattaforme
| Dove | Come | Chi |
|---|---|---|
| **Android** | app installabile (APK) | tester |
| **Windows** | CLI `zibaldone` / `zbone` da PowerShell, poi interfaccia grafica | Alex e chi usa il PC |

Scelta tecnica ([ADR-0004](../decisioni/ADR-0004-flet-e-sqlite.md)): **un solo codice Python** per il cuore dell'app (`core/`, `storage/`) e un'interfaccia con **Flet**, che produce sia l'app Windows sia l'APK Android dallo stesso codice. La CLI resta un'interfaccia in più sopra lo stesso cuore.

## Versioni
- **Numerazione** ([ADR-0010](../decisioni/ADR-0010-numerazione-delle-versioni.md)): prima della 1.0 ogni versione `0.Y.Z` aggiunge una capacità `Z` dentro una fase `Y` (`0.0.x` fondamenta, `0.1.x` app per i tester, `0.2.x` sprint delle 8 aree). La **1.0** è l'app davvero usabile ogni giorno. Dopo la 1.0 si torna al SemVer classico: correzione `1.0.1`, funzione nuova `1.1.0`.
- Ogni versione ha un tag git, una voce nel CHANGELOG e una nota in `docs/versioni/`.

## Canale per i tester Android
1. **Fase 1 — APK su GitHub Releases**: ogni tag produce un APK allegato alla release. I tester lo installano consentendo "app da origini sconosciute". All'avvio l'app controlla se c'è una versione nuova e lo dice.
2. **Fase 2 — Google Play, test interno**: aggiornamenti automatici dal Play Store per un gruppo chiuso di tester. Richiede un account sviluppatore Google (costo una tantum) e la policy sulla privacy pubblicata.

## Dati e aggiornamenti
- Ogni archivio dati porta uno `schema_version`. Un aggiornamento che cambia il formato include una **migrazione** automatica, con backup prima di applicarla.
- Un aggiornamento non deve mai cancellare i dati dell'utente. Su Android i dati restano nella memoria privata dell'app: disinstallare l'app li cancella, va detto ai tester insieme all'export.
