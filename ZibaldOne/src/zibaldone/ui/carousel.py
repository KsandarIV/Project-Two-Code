"""Pages one long press away: a page body that changes page on «long press, then drag», with its bar of pages at the bottom.

Used by Modelli (the areas) and Collezioni (the kinds of collection). Scrolling up and down stays immediate; only a long press followed by a sideways drag turns the page, in a loop.
"""

from typing import Any, Callable, Dict, List, Optional

import flet as ft

from zibaldone.ui import theme as T
from zibaldone.ui import widgets as W

SWIPE_DISTANCE = 60  # pixels of drag, after the long press, that change the page
TINT = 0.07


def bar_item(face: ft.Control, color: str, label: str, selected: bool, choose: Callable[[], None]) -> ft.Control:
    return ft.Container(
        face,
        padding=4,
        border_radius=T.RADIUS_SMALL,
        bgcolor=W.fade(color, 0.22) if selected else None,
        border=ft.Border.all(1, color) if selected else None,
        tooltip=label,
        on_click=lambda _: choose(),
        ink=True,
    )


def page_body(content: ft.Control, items: List[ft.Control], color: str, step: Callable[[int], None]) -> ft.Control:
    """`content` in a tinted page with the bar `items` fixed under it; `step(±1)` is called on a long press and drag."""
    origin: Dict[str, float] = {}

    def x_of(event: Any) -> Optional[float]:
        position = getattr(event, "global_position", None)
        return getattr(position, "x", None)

    def pressed(event: Any) -> None:
        start = x_of(event)
        if start is not None:
            origin["x"] = start

    def released(event: Any) -> None:
        end, start = x_of(event), origin.pop("x", None)
        if end is None or start is None:
            return
        dx = end - start
        if dx <= -SWIPE_DISTANCE:
            step(1)
        elif dx >= SWIPE_DISTANCE:
            step(-1)

    pages = ft.GestureDetector(content=content, on_long_press_start=pressed, on_long_press_end=released, expand=True)
    bar = ft.Container(
        ft.Row(items, alignment=ft.MainAxisAlignment.SPACE_AROUND, spacing=2, scroll=ft.ScrollMode.AUTO),
        padding=ft.Padding.symmetric(horizontal=8, vertical=6),
        border=ft.Border(top=ft.BorderSide(1, T.BORDER)),
    )
    return ft.Container(ft.Column([pages, bar], spacing=0, expand=True), bgcolor=W.fade(color, TINT), expand=True)


def next_page(pages: List[str], current: str, delta: int) -> str:
    return pages[(pages.index(current) + delta) % len(pages)] if current in pages else pages[0]


def hook_back(ctx: Any, home: str, current: str, go_home: Callable[[], None]) -> Optional[Callable[[], bool]]:
    """Back from any page but `home` goes to `home` first."""
    if current == home:
        return None

    def back() -> bool:
        go_home()
        return True

    return back


def centered(home: str, others: List[str]) -> List[str]:
    """The pages in order, with the home one in the middle: half of the others before it, half after."""
    half = len(others) // 2
    return [*others[:half], home, *others[half:]]
