# Icona dell'app

Alex le vuole tenere tutte e quattro. L'icona predefinita è la **C · monogramma** (ZO grande con otto pallini, uno per mascotte, su sfondo `#0D0E15`). Le altre sono la A (ruota con anello), la B (ruota con spicchi staccati) e la D (tessere 3x3).

## Dove sta cosa
- `src/assets/icon.png` (1024) → icona di Windows e di default per `flet build`.
- `src/assets/icon_android.png` → primo piano trasparente dell'icona adattiva di Android; lo sfondo è `icon_background` in `pyproject.toml`.
- `scelta/A|B|C|D/` → i file pronti di ogni proposta: `icon.png`, `icon_android.png` e `icona.ico` (per Windows).
- `svg/` e `png/` → sorgenti, misure 1024/512/256/128/64/48, `icon.ico`, sfondo Android.
- `proposte/` → le proposte di Alex (Gemini) e le anteprime delle mie.

## Come si sceglie
Oggi, a mano: copiare i due PNG di `scelta/<lettera>/` in `src/assets` e rifare la build.

**Fatto in 0.3.3 (solo la scelta e l'icona della finestra)**: la scelta si fa al primo avvio e in Impostazioni → Personalize (Kosmesis), `ui/views/app_icon.py`; il collegamento e l'icona installata restano da fare. Limiti da tenere presenti:
- l'icona installata (exe di Windows, icona del lancio su Android) è fissa dentro la build: l'app non può cambiarla mentre gira. Su Android servirebbe una build con quattro «alias» del lancio, su Windows un collegamento con l'icona scelta;
- cambia a runtime solo l'icona nella finestra e il logo mostrato nell'app.
Su Windows Alex ha approvato due strade (2026-10-25):
1. **Finestra e barra in esecuzione**: l'app carica a runtime il `.ico` scelto (`scelta/<lettera>/icona.ico`) e lo imposta come icona della finestra.
2. **Collegamento**: un pulsante in Informazioni crea o aggiorna il collegamento sul desktop o nel menu Start, con l'icona che punta a un `.ico` salvato nei dati dell'app (non nella cartella dell'exe, che può essere spostata o riscritta dagli aggiornamenti).

Prima di scrivere il codice va verificato a mano su Windows che la finestra di Flet accetti il `.ico` a runtime e che la barra lo mostri. Intanto c'è la guida a mano: `docs/utente/cambiare-icona.md`. Su Android la scelta a runtime resta fuori.
