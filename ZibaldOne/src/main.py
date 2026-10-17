"""Entry point for `flet build` and `flet run` (see [tool.flet.app] in pyproject.toml)."""

import flet as ft

from zibaldone.ui.app import main

ft.run(main)
