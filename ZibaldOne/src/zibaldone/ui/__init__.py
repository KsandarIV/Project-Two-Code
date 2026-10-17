"""ZibaldOne's graphical interface (Flet), from version 0.1.0.

Pure modules (no Flet, unit-tested): `theme`, `navigation`, `forms`,
`viewmodels`, `services`. Flet modules: `widgets`, `context`, `app`, `views/`.

Start it with `python -m zibaldone.ui` or `zibaldone.ui.app.run()`;
Flet calls `zibaldone.ui.app.main(page)`.
"""

from typing import Any


def main(page: Any) -> None:
    """Flet entry point (imports Flet only when called)."""
    from zibaldone.ui.app import main as app_main

    app_main(page)


def run(**kwargs: Any) -> None:
    from zibaldone.ui.app import run as app_run

    app_run(**kwargs)
