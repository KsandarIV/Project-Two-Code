# ADR-0002 — Local-first, trasparenza e privacy

- **Data**: 2026-10-17 · **Stato**: accettata
- **Contesto**: un diario contiene dati molto personali. Alex vuole che l'app sia sicura, salvi tutto in locale e lo dica chiaramente, con la possibilità di usare Google Drive.
- **Decisione**: dati solo sul PC nella cartella dati dell'utente; avviso e consenso al primo avvio; comando `zbone privacy`; nessuna telemetria; Google Drive tramite la cartella sincronizzata di Drive per desktop; cifratura opzionale con passphrase. Dettagli in [privacy e sicurezza](../tecnica/privacy-e-sicurezza.md).
- **Conseguenze**: chi sviluppa non riceve dati degli utenti; la responsabilità del backup è dell'utente e l'app lo deve ricordare.
