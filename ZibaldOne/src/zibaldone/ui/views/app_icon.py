"""The app icon (A014): four choices, the same row at the first start and in Kosmesis."""

from typing import Any, Callable

import flet as ft

from zibaldone.ui import services
from zibaldone.ui import theme as T
from zibaldone.ui import widgets as W
from zibaldone.ui.context import AppContext

ICONS_DIR = "icons"  # assets/icons/<A|B|C|D>.png and .ico


def apply_window_icon(ctx: AppContext) -> None:
    """Put the chosen icon on the desktop window; a phone or a browser has no window icon to change."""
    window = getattr(ctx.page, "window", None)
    path = W.ASSETS_DIR / ICONS_DIR / f"{services.app_icon(ctx.folder)}.ico"
    if window is None or not path.exists():
        return
    try:
        window.icon = str(path)
        ctx.update()
    except Exception:
        pass


def picker(ctx: AppContext, on_pick: Callable[[str], Any]) -> ft.Control:
    """The four icons side by side, the chosen one framed."""
    current = services.app_icon(ctx.folder)

    def tile(letter: str) -> ft.Control:
        chosen = letter == current
        return ft.Container(
            ft.Image(src=f"{ICONS_DIR}/{letter}.png", width=72, height=72, fit=ft.BoxFit.CONTAIN, tooltip=f"Icona {letter}"),
            padding=6,
            border=ft.Border.all(2, T.ACCENT if chosen else T.TEXT_DIM),
            border_radius=T.RADIUS_SMALL,
            on_click=lambda _, letter=letter: on_pick(letter),
        )

    return ft.Row([tile(letter) for letter in services.APP_ICONS], spacing=12, wrap=True)


def choose(ctx: AppContext, letter: str) -> None:
    """Save the choice, change the window icon and redraw."""
    services.set_app_icon(ctx.folder, letter)
    apply_window_icon(ctx)
    ctx.refresh()
