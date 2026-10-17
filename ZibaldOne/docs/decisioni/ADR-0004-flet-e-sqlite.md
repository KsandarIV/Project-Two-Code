# ADR-0004 — Flet per l'interfaccia, SQLite per i dati

- **Data**: 2026-10-17 · **Stato**: accettata (scelta di Alex)
- **Contesto**: ZibaldOne deve girare su Windows e Android, in futuro Linux; Alex conosce Python; i tester usano Android.
- **Decisione**:
  - Interfaccia grafica con **Flet** (Python): un solo codice per Windows, Android (APK) e Linux.
  - Dati in **SQLite** nella memoria locale di ogni dispositivo, con **export in Markdown** (leggibile, apribile in Obsidian) e backup.
  - Il cuore (`core/`, `storage/`) resta indipendente da Flet: CLI e UI sono due facce dello stesso cuore.
- **Alternative scartate**: web app PWA (UI in HTML/JavaScript), Kotlin nativo (linguaggio nuovo e due codici separati), file Markdown come fonte principale (scomodi su Android).
- **Conseguenze**: lo schema SQLite è versionato con migrazioni fin dalla v0.0.2; i test del cuore non dipendono dall'interfaccia.
