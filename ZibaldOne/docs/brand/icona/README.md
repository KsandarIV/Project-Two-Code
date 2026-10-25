# Icona dell'app

L'icona in uso è la proposta **A · ruota**: gli otto spicchi con i disegni delle mascotte (ZibaldOne/SVG, ripresi senza modifiche) e il monogramma ZO al centro, su sfondo `#0D0E15`.

- `src/assets/icon.png` (1024) → icona di Windows e di default per `flet build`.
- `src/assets/icon_android.png` → primo piano trasparente dell'icona adattiva di Android; lo sfondo è `icon_background` in `pyproject.toml`.
- `svg/` e `png/` → sorgenti, misure 1024/512/256/128/64/48, `icon.ico`, primo piano e sfondo Android, e le proposte B, C, D.
- Per cambiare icona basta sostituire i due PNG in `src/assets`.
