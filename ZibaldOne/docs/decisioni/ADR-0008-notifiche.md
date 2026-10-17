# ADR-0008 — Notifiche che spronano a scrivere

- **Data**: 2026-10-17 · **Stato**: accettata (richiesta di Alex), dettagli tecnici da verificare su Android alla v0.1.1
- **Contesto**: un diario funziona se lo si apre ogni giorno. La Journal App ruotava intorno a 3 momenti (inizio, metà, fine giornata). Serve un promemoria che sproni senza diventare fastidioso o colpevolizzante.
- **Decisione**:
  - **Promemoria per momento**: Mattina, Metà giornata, Sera, con orari predefiniti 08:30, 13:30, 21:30. Ogni momento si accende, si spegne e cambia orario; si scelgono i giorni della settimana.
  - **Intelligenti, non insistenti**: al massimo un promemoria per momento al giorno; nessun promemoria se la voce di quel momento è già scritta; **ore di silenzio** (predefinite 22:30–08:00); dopo 3 promemoria ignorati di fila l'app propone di diradarli.
  - **Tono gentile**: messaggi brevi che ruotano, senza sensi di colpa ("Due righe sulla tua mattina?"). La **serie di giorni** si festeggia, ma perderla non genera rimproveri.
  - **Privacy**: il testo della notifica non contiene mai dati delle voci (si vede anche a schermo bloccato). Nessun servizio push esterno: tutto è calcolato sul dispositivo.
  - **Cuore separato dalla consegna**: `core/reminders.py` decide in modo deterministico *cosa* va notificato e *quando* (funzione pura, testabile). La consegna è un adattatore:
    - CLI: `zbone remind status`, `zbone remind fire` (stampa o mostra il promemoria dovuto);
    - Windows: notifica di sistema con `desktop-notifier` e, ad app chiusa, attività pianificate di Windows create da `zbone remind install` (rimosse con `zbone remind uninstall`);
    - interfaccia Flet: avviso in app all'apertura e notifiche mentre l'app è aperta;
    - Android: notifiche locali native con `android-notify`. **Da verificare sul telefono**: le notifiche ad app chiusa su Android possono richiedere lavoro nativo in più.
- **Alternative scartate**: notifiche push da un server (servirebbe un server nostro); l'estensione `flet-local-notifications` (richiede Flet 0.28, noi usiamo Flet 1.0).
- **Conseguenze**: nuove impostazioni `reminders` in `settings.json`; un registro locale di cosa è stato notificato; l'avviso privacy cita i promemoria.
