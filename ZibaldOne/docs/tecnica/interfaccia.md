# Interfaccia grafica (dalla 0.1.0)

L'app per Windows e Android, scritta con Flet 1.0.4. Usa gli stessi `core/`, `storage/` e `cloud/` della CLI, senza duplicarne la logica: la UI decide solo cosa mostrare e quando.

## Come si avvia
```
python -m zibaldone.ui                  # finestra desktop
python -m zibaldone.ui --web --port 8550 # nel browser, utile per provare e fare screenshot
python -m zibaldone.ui --route /voci     # parte da una pagina qualsiasi
```
- `ZIBALDONE_UI_START=/organon/mnemosyne` ha lo stesso effetto di `--route`.
- `ZIBALDONE_HOME` sceglie la cartella dati, come per la CLI. Su Android, se non è impostata, i dati vanno nella cartella privata che dà Flet (`FLET_APP_STORAGE_DATA`).
- Gli entry point sono `zibaldone.ui.app:main(page)` (per `flet run` e `flet build`) e `zibaldone.ui.app:run(web, port, route)`.

## Struttura
```
src/zibaldone/ui/
  theme.py        colori, misure e larghezza oltre cui la barra in basso diventa laterale
  navigation.py   sezioni, parti di Organon, rotte (parse_route / route_path); niente Flet
  forms.py        da modello a campi del modulo e ritorno: validazione, numeri, tag, date
  viewmodels.py   cosa mostra ogni schermata (Oggi, liste, dettagli, piani dei pacchetti…)
  cloud_model.py  testi e scelte di Le Nuvole e della cifratura; i comandi `zbone …` diventano posti nell'app
  services.py     tutto ciò che tocca disco, database o rete; si chiama in un thread
  context.py      AppContext: navigazione, avvisi, dialoghi, run_blocking, data_changed
  widgets.py      i mattoni grafici comuni (schermata, pannelli, pulsanti, campi larghi)
  views/          una schermata per modulo: today, entries, entry_form, collections,
                  templates, template_editor, settings, cloud, encryption, onboarding
  app.py          Shell: layout adattivo, cronologia, primo avvio, promemoria, backup automatico
```
Le parti senza Flet (`navigation`, `forms`, `viewmodels`, `cloud_model`, `theme`) sono pure e si provano senza interfaccia.

## Regole
- **Thread**: il lavoro bloccante (SQLite, backup, Google) passa da `ctx.run_blocking` o `asyncio.to_thread`. Uno `Store` per operazione e per thread: `services.open_store(folder)` si apre e si chiude dentro il thread che lo usa.
- **Primo avvio**: consenso privacy → accesso (solo se `login_required`) → dove vanno le copie (solo dopo un accesso con permesso Drive) → backup prima di un aggiornamento dello schema → diario → Oggi. Backup, export e privacy non chiedono mai l'accesso.
- **Dopo un salvataggio** le viste chiamano `ctx.data_changed()`: parte il backup del giorno e, se c'è una destinazione, la copia fuori.
- **Errori**: si mostra `str(errore)`, già in italiano, passato da `cloud_model.error_text`.
- **Testi**: italiano, tono gentile, nome semplice più nome filosofico (Oggi · Hic et nunc). Il codice è in inglese.

## Aggiungere una schermata
1. In `views/` scrivi `build(ctx, route) -> ft.Control`, usando `W.screen(...)` e i widget comuni.
2. In `navigation.py` aggiungi la rotta a `parse_route` e a `route_path`; per una nuova voce del menu, anche a `SECTIONS`.
3. Registrala in `views/__init__.py` (`SCREENS`); se va a schermo intero senza menu, anche in `ONBOARDING_SCREENS`.
4. Metti la logica in `viewmodels.py` (o in un modulo puro accanto) e il disco in `services.py`.
5. Test: la logica in `tests/test_ui_viewmodels.py`; aggiungi la rotta a `paths` in `test_every_screen_builds_headless` (`tests/test_ui_views.py`), che costruisce ogni schermata alle due larghezze.

## Test
- `tests/test_ui_logic.py`, `tests/test_ui_viewmodels.py`, `tests/test_ui_cloud.py`: parti pure e servizi.
- `tests/test_ui_views.py`: costruisce le schermate con una pagina finta (nessuna finestra), percorre il primo avvio, la navigazione e il salvataggio di una voce.

## Prossime versioni
- 0.1.2 ✅: la casella di Voci cerca in tutti i blocchi ([ricerca e collegamenti](ricerca-e-collegamenti.md)); la pagina di una voce mostra chi la cita e chi la nomina.
- 0.1.3 ✅: **Rizoma**, il grafo su una tela toccabile (`/grafo`, `/grafo/<id>`), da Voci e dalla pagina di una voce ([il grafo](grafo.md)).
- 0.1.4 ✅: **Theoria**, le statistiche della settimana o del mese (`/theoria`, da Oggi) e la revisione preparata dai numeri ([statistiche e revisioni](statistiche.md)).
- 0.1.5 ✅: **Velo d'ignoranza**, l'anonimizzatore da provare in Impostazioni (`/organon/velo`) ([anonimizzatore](anonimizzatore.md)).
- 0.2.0 ✅: **Eudaimonia**, le otto aree (`/aree`, da Oggi) e la pagina di ogni area (`/aree/<area>`); il modulo si apre con l'area già scelta (`/scrivi/<modello>/<area>`) ([le 8 aree](aree.md)). Le funzioni future si mostrano con `W.upcoming_card` («In arrivo · versione …»).
- 0.2.1 ✅: **Agorà**, la pagina di una persona (`/persone/<id>`), dalla voce Persona e dal riquadro Persone delle aree ([le persone](persone.md)).
- 0.2.2 ✅: l'**albero di famiglia** (`/albero`) e la **rete** delle persone (`/rete`, `/rete/<area>`), dalla pagina di una persona e dal riquadro Persone delle aree; la rete riusa il disegno del grafo (`canvas_shapes` in `ui/views/graph.py`).
- 0.2.3 ✅: i **segreti** (`ui/views/vault.py`): **Apri** nella pagina di una voce chiede il PIN o la passphrase, il modulo ha `SecretEditor`, Mnemosyne il riquadro del PIN. Le chiavi aperte stanno in `ctx.memory["vault"]` ([i segreti](segreti.md)).
- 0.2.4 ✅: gli **allegati** (`ui/views/media_view.py`): «Aggiungi file» nel modulo (`ctx.pick_files`, il `FilePicker` di Flet), miniature e **Apri** nella pagina della voce (`ctx.open_file`: programma predefinito sul PC, menu Condividi sul telefono) ([gli allegati](allegati.md)).
- 0.2.5 ✅: **Collezioni** con i riquadri Preferiti, Lista dei desideri e Tempo speso, la finestra **Importa da un file** (`ui/views/import_dialog.py`), le stelle a metà, il cuore del preferito (`FavoriteEditor`) e la recensione con spoiler nascosta nella pagina della voce ([svago avanzato](svago.md)).
- 0.2.6 ✅: il **bilancio** (`/finanze`, `/finanze/AAAA-MM`, da Aree → Finanze, `ui/views/finance.py`): chiede il PIN con `unlock_secrets`, somma in memoria, `Spesa`/`Entrata` rapide in un dialogo ([le finanze](finanze.md)).
- 0.2.7 ✅: **Abitudini** (`/abitudini`, `ui/views/habits.py`): riquadro in Oggi, schermata con serie e ultimi 7 giorni, riga nella pagina dell'area ([le abitudini](abitudini.md)).
- 0.2.8 ✅: **Viste e home su misura** (`/viste`, `ui/views/saved_views.py`, `home_layout.py`, `tiles.py`): Oggi segue il layout scelto in Impostazioni → Kosmesis → Oikos ([viste e home](viste-e-home.md)).
- La fase 0.2 si chiude con la 0.2.8: l'import dei vecchi diari (0.2.9) non serve ([requisiti](requisiti-v0.2.md)).
