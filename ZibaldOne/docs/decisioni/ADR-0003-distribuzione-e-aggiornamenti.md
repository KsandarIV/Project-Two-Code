# ADR-0003 — Distribuzione ai tester e aggiornamenti

- **Data**: 2026-10-17 · **Stato**: accettata
- **Contesto**: alcuni amici di Alex proveranno l'app **su Android**; servono aggiornamenti e patch a distanza.
- **Decisione**: SemVer, GitHub Releases come canale (APK per Android, poi eventualmente Google Play test interno), controllo delle nuove versioni all'avvio, migrazioni dei dati versionate. La tecnologia dell'app è in [ADR-0004](ADR-0004-flet-e-sqlite.md) (Flet). Dettagli in [distribuzione](../tecnica/distribuzione.md).
- **Conseguenze**: il formato dei dati deve essere versionato fin dalla prima voce salvata.

## Nota 2026-10-17 (0.1.1)
Messo in pratica: GitHub Actions costruisce l'APK a ogni tag `zibaldone-v*` e lo allega a una *pre-release*; l'app controlla le release una volta al giorno, si può spegnere, e l'avviso privacy (versione 5) lo dice. Il controllo non usa account né manda dati dell'utente. Dettagli in [distribuzione](../tecnica/distribuzione.md) e [rilascio Android](../sviluppo/rilascio-android.md).
