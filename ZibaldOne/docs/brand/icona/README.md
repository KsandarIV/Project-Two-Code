# Icona dell'app

Alex le vuole tenere tutte e quattro. L'icona predefinita è la **C · monogramma** (ZO grande con otto pallini, uno per mascotte, su sfondo `#0D0E15`). Le altre sono la A (ruota con anello), la B (ruota con spicchi staccati) e la D (tessere 3x3).

## Dove sta cosa
- `src/assets/icon.png` (1024) → icona di Windows e di default per `flet build`.
- `src/assets/icon_android.png` → primo piano trasparente dell'icona adattiva di Android; lo sfondo è `icon_background` in `pyproject.toml`.
- `scelta/A|B|C|D/` → i due PNG pronti di ogni proposta (`icon.png`, `icon_android.png`).
- `svg/` e `png/` → sorgenti, misure 1024/512/256/128/64/48, `icon.ico`, sfondo Android.
- `proposte/` → le proposte di Alex (Gemini) e le anteprime delle mie.

## Come si sceglie
Oggi, a mano: copiare i due PNG di `scelta/<lettera>/` in `src/assets` e rifare la build.

**Da fare, non ancora implementato.** La scelta andrà nelle Impostazioni, nella parte **Informazioni · ZibaldOne** (`ui/views/settings.py`, `about`), accanto alle mascotte: una riga «Icona» con le quattro anteprime. Limiti da tenere presenti:
- l'icona installata (exe di Windows, icona del lancio su Android) è fissa dentro la build: l'app non può cambiarla mentre gira. Su Android servirebbe una build con quattro «alias» del lancio, su Windows un collegamento con l'icona scelta;
- cambia a runtime solo l'icona nella finestra e il logo mostrato nell'app.
Prima di costruirla va deciso con Alex se la scelta vale solo per il logo nell'app o anche per l'icona installata.
