# ADR-0010 — Numerazione delle versioni: la 1.0 è l'app davvero usabile

- **Data**: 2026-10-17 · **Stato**: accettata (scelta di Alex)
- **Contesto**: la roadmap arrivava alla 1.5 e chiamava "v2" lo sprint successivo, mentre l'app non ha ancora un'interfaccia grafica e non è stata usata da nessuno. Numeri così alti promettono una maturità che non c'è.
- **Decisione**:
  - Tutto scende di un livello: la vecchia 0.N diventa **0.0.N**, la vecchia 1.N diventa **0.1.N**, la "v2" diventa la fase **0.2**.
  - Prima della 1.0 una versione `0.Y.Z` aggiunge la capacità `Z` dentro la fase `Y`:
    - **0.0.x** fondamenta (CLI, dati, modelli, backup, cifratura, cloud, prima interfaccia);
    - **0.1.x** app per i tester (APK, notifiche, ricerca, grafo, statistiche, anonimizzatore);
    - **0.2.x** sprint delle 8 aree dalla vecchia Journal App.
  - La **1.0** arriva quando l'app è davvero usabile ogni giorno: i criteri sono nella [roadmap](../tecnica/roadmap.md#verso-la-10).
  - Le correzioni prima della 1.0 entrano nella versione successiva. Dopo la 1.0 si passa al SemVer classico: correzione `1.0.1`, funzione nuova `1.1.0`, cambiamento incompatibile `2.0.0`.
  - Rilascio: `py scripts/release.py patch` per la capacità successiva, `minor` per la fase successiva ([versionamento](../sviluppo/versionamento.md)).
- **Conseguenze**:
  - Le versioni già fatte sono state rinumerate prima di pubblicarle su GitHub: commit, tag (`zibaldone-v0.0.2` … `zibaldone-v0.0.5`), CHANGELOG e note in `docs/versioni/`. Nessuna versione con i vecchi numeri era stata pubblicata.
  - Il codice Android (`versionCode`) si calcola dalla versione: `Y*1000 + Z` prima della 1.0, sempre crescente.
- **Alternative scartate**: tenere i vecchi numeri (1.0 troppo presto); usare `0.X` a due cifre (non è SemVer valido e confonde gli strumenti).
