# Stato di ZibaldOne alla 0.2.8 (2026-10-24)

Scritto da Sviluppo. Per ogni cosa dico **come l'ho verificata**: `test` = c'è un test automatico che passa (tutta la suite: **647 test verdi** sull'albero 0.2.8, Python 3.12); `provato` = l'ho eseguita io oggi dal terminale su una cartella dati vuota e temporanea (`ZIBALDONE_HOME`); `schermata` = l'ho vista nello screenshot di Alex (Windows, 24 ottobre). Una finestra vera dell'app non l'ho mai aperta da questa sessione: la UI è provata solo dai test che costruiscono ogni schermata senza finestra.

## 1. Funziona davvero (verificato)

**Dal terminale** (`zbone …`, provato oggi su cartella vuota: installati i pacchetti, scritto un rituale, segnata l'abitudine, salvata e aperta una vista, composta la home):
- Primo avvio: avviso sulla privacy e consenso, poi la cartella dati; senza consenso non salva nulla. *Provato, test* (`test_ui_views`, `test_privacy`).
- Pacchetti pronti (Diario, Aree, Persone, Collezioni, Finanze, Segreti, Io, Askesis, Theoria): elenco e installazione con conferma. *Provato, test* (`test_packs`).
- Voci a blocchi da modello (`entry add`), modelli e pacchetti da condividere, ricerca (Zetesis), collegamenti, grafo, statistiche, revisioni. *Test* (`test_cli_entries`, `test_search`, `test_links`, `test_graph`, `test_stats`, `test_overviews`).
- Abitudini: `abitudini`, `abitudini segna acqua 8` → serie di giorni. *Provato, test* (`test_habits`).
- Viste salvate («libri in corso») e layout della home: `viste salva/mostra`, `home aggiungi`. *Provato, test* (`test_views`, `test_home`).
- Finanze con importi cifrati: saldo, mese, debiti, ricorrenti. *Provato (saldo 0 a vuoto), test* (`test_finance`).
- Aree, persone, ricorrenze, segreti con PIN, allegati, backup cifrati e ripristino, esportazione Markdown/CSV, anonimizzatore, promemoria (calcolo degli orari). *Test* (`test_areas`, `test_people`, `test_relations`, `test_secrets`, `test_crypto`, `test_media`, `test_backups`, `test_export`, `test_anonymizer`, `test_reminders`).
- Import da Goodreads, Letterboxd, MyAnimeList, Steam con file di prova. *Test* (`test_recreation`).

**Nell'app** (finestra o `--web`):
- Si apre su Windows e mostra le otto aree con le mascotte. *Schermata.* Le avvisa che manca la Scuola «Liceo · Aree» e offre di installarla. *Schermata.*
- Ogni schermata (Oggi, voci, modelli, aree, persone, albero, rete, finanze, abitudini, viste, la tua home, statistiche, anonimizzatore, impostazioni, Nuvole) si costruisce senza errori, in layout largo e stretto; navigazione e tasto indietro Android; scrittura e cancellazione di voci con conferma; PIN per segreti e importi; riquadri di Oggi in ordine scelto. *Test* (`test_ui_views`, `test_ui_logic`, `test_ui_viewmodels`, `test_ui_habits`, `test_ui_home`, `test_ui_cloud`).

## 2. Non verificato (esiste nel codice, ma non l'ho visto funzionare davvero)
- L'app su **telefono Android vero** e l'APK (il workflow esiste; non ho visto un APK installato).
- L'**accesso con Google** e le copie su **Google Drive** dal vivo: i test usano finti. L'accesso è richiesto solo se l'app ha un client OAuth configurato; senza, parte lo stesso (`cloud/account.py`). Il client OAuth lo deve ancora creare Alex.
- I **promemoria** come notifiche vere (Windows pianificazioni, Android): provato solo il calcolo degli orari.
- Il **controllo versioni** contro GitHub (test con risposte finte).
- Prestazioni con tanti dati (migliaia di voci o di movimenti): mai misurate.
- Un ripristino da backup su un dispositivo nuovo.
- Come si presenta, a occhio, ognuna delle schermate nuove (viste, la tua home, abitudini): mai viste in una finestra.

## 3. Cosa manca (rispetto a «app che un tester apre e usa»)
- **Eseguibile**: oggi si parte con `zbone app` dopo aver installato Python e il pacchetto in un ambiente a mano. Alex vuole un eseguibile (niente terminale, niente venv). C'è un thread dedicato («Eseguibile Windows»); non so a che punto sia.
- **Primo avvio senza comandi**: i pacchetti (Diario, Aree, …) vanno installati uno per uno; l'app lo propone nelle pagine ma una persona nuova non ha un percorso guidato.
- Piccoli difetti visti oggi: «1 giorni di fila» (plurale); l'aiuto di `viste salva` cita `--modello libro` anche se il pacchetto Collezioni non c'è (errore «nessun modello 'libro'», giusto ma poco guidato).
- L'avviso «I tuoi vecchi diari · in arrivo 0.2.9» in Aree: da togliere (c'è la patch).
- **Android e CI/CD completi** (`release.yml`, cartella `platforms/`, protezione di `main`, segreti per l'APK): in mano a DevOps e ad Alex.
- Ricorrenze: solo i compleanni (niente anniversari o cene). Obiettivi: avanzamento e scadenza, non traguardi con scadenza propria.
- Sblocco con impronta o volto (serve Android vero). **Maieutica** (IA che fa domande) dopo la 1.0.
- Licenza e repository pubblico: decisioni di Alex.
