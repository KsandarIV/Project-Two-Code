# Mappa del codice

Generata da `scripts/code_map.py` il 2026-10-30. Si rigenera a ogni PR di rilascio.
120 moduli in `src/zibaldone/`. Regola: `core` non importa `ui`, `cli`, `storage` (violata da: zibaldone.core.habits -> zibaldone.storage.database, zibaldone.core.views -> zibaldone.storage.database).

## Livelli
- **core**: 24 moduli, 8720 righe
- **storage**: 11 moduli, 3444 righe
- **cli**: 25 moduli, 3689 righe
- **cloud**: 8 moduli, 1568 righe
- **notify**: 5 moduli, 643 righe
- **packs**: 1 moduli, 0 righe
- **ui**: 44 moduli, 11393 righe
- **(radice)**: 2 moduli, 6 righe

## Moduli più usati (import in ingresso)
- `zibaldone.ui` (35): ZibaldOne's graphical interface (Flet), from version 0.1.0.
- `zibaldone.storage.database` (31): SQLite storage for templates and entries, with numbered migrations.
- `zibaldone.ui.context` (29): What every view receives: the data folder, the page and a few app-wide actions.
- `zibaldone.core` (24): Domain: blocks, templates, entries, privacy texts. Standard library only.
- `zibaldone.cli.common` (23): Helpers shared by every CLI command: consent, account, opening the store, answers, errors.
- `zibaldone.core.templates` (23): Templates (user recipes made of blocks) and entries (filled-in templates).
- `zibaldone.ui.navigation` (22): Sections, routes and layout choice. Pure: no Flet import.
- `zibaldone.core.blocks` (21): Block types: the bricks every template is made of.
- `zibaldone.core.brand` (19): Brand identity: names, mascots and quotes taken from philosophy.
- `zibaldone.storage` (18): Persistence in the user's data folder: paths, settings, folder usage.
- `zibaldone.core.areas` (15): Eudaimonia (0.2.0): the 8 life areas as a concept of the whole app.
- `zibaldone.storage.paths` (14): Where ZibaldOne keeps the user's data on each platform.

## Moduli più grandi
- `zibaldone.ui.viewmodels`: 1786 righe
- `zibaldone.storage.database`: 1060 righe
- `zibaldone.storage.backups`: 1004 righe
- `zibaldone.core.stats`: 883 righe
- `zibaldone.ui.views.entry_form`: 789 righe
- `zibaldone.core.reminders`: 766 righe
- `zibaldone.core.blocks`: 734 righe
- `zibaldone.core.anonymizer`: 726 righe

Per lo scopo di un modulo: la prima riga del suo docstring.
