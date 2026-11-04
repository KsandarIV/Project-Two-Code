# Mappa del codice

Generata da `scripts/code_map.py` il 2026-11-04. Si rigenera a ogni PR di rilascio.
129 moduli in `src/zibaldone/`. Regola: `core` non importa `ui`, `cli`, `storage` (rispettata).

## Livelli
- **core**: 26 moduli, 8955 righe
- **storage**: 14 moduli, 4444 righe
- **cli**: 25 moduli, 3710 righe
- **cloud**: 8 moduli, 1574 righe
- **notify**: 5 moduli, 643 righe
- **packs**: 1 moduli, 0 righe
- **ui**: 48 moduli, 12896 righe
- **(radice)**: 2 moduli, 6 righe

## Moduli più usati (import in ingresso)
- `zibaldone.ui` (38): ZibaldOne's graphical interface (Flet), from version 0.1.0.
- `zibaldone.storage.database` (30): SQLite storage for templates and entries, with numbered migrations.
- `zibaldone.ui.context` (30): What every view receives: the data folder, the page and a few app-wide actions.
- `zibaldone.core` (27): Domain: blocks, templates, entries, privacy texts. Standard library only.
- `zibaldone.storage` (23): Persistence in the user's data folder: paths, settings, folder usage.
- `zibaldone.cli.common` (23): Helpers shared by every CLI command: consent, account, opening the store, answers, errors.
- `zibaldone.core.templates` (23): Templates (user recipes made of blocks) and entries (filled-in templates).
- `zibaldone.ui.navigation` (22): Sections, routes and layout choice. Pure: no Flet import.
- `zibaldone.core.brand` (20): Brand identity: names, mascots and quotes taken from philosophy.
- `zibaldone.core.blocks` (20): Block types: the bricks every template is made of.
- `zibaldone.core.areas` (15): Eudaimonia (0.2.0): the 8 life areas as a concept of the whole app.
- `zibaldone.storage.paths` (14): Where ZibaldOne keeps the user's data on each platform.

## Moduli più grandi
- `zibaldone.ui.viewmodels`: 1790 righe
- `zibaldone.storage.database`: 1072 righe
- `zibaldone.storage.backups`: 1045 righe
- `zibaldone.core.stats`: 883 righe
- `zibaldone.core.reminders`: 796 righe
- `zibaldone.ui.views.entry_form`: 789 righe
- `zibaldone.ui.views.settings`: 736 righe
- `zibaldone.core.blocks`: 734 righe

Per lo scopo di un modulo: la prima riga del suo docstring.
