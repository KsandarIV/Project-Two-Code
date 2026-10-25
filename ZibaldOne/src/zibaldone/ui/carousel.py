"""Pages one sideways drag away: a page body that changes page on a sideways drag, with its bar of pages at the bottom.

Used by Modelli (the areas) and Collezioni (the kinds of collection). Scrolling up and down is untouched; a sideways drag turns the page, in a loop.
"""

import asyncio
from typing import Any, Callable, Dict, List, Optional

import flet as ft

from zibaldone.ui import theme as T
from zibaldone.ui import widgets as W

SWIPE_DISTANCE = 60  # pixels of sideways drag that change the page
ENTER_KEY = "carousel_enter"
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


def page_body(content: ft.Control, items: List[ft.Control], color: str, step: Callable[[int], None], ctx: Any = None) -> ft.Control:
    """`content` in a tinted page with the bar `items` fixed under it; `step(±1)` is called on a sideways drag.

    The page follows the finger, shrinking and fading as it leaves; the next one slides in from the side it came from
    (`ctx.memory` carries the direction from one build to the next).
    """
    enter = int(ctx.memory.pop(ENTER_KEY, 0)) if ctx is not None else 0
    body = ft.Container(
        content,
        expand=True,
        animate_offset=ft.Animation(220, ft.AnimationCurve.EASE_OUT),
        animate_opacity=ft.Animation(220, ft.AnimationCurve.EASE_OUT),
        animate_scale=ft.Animation(220, ft.AnimationCurve.EASE_OUT),
        offset=ft.Offset(0.3 * enter, 0) if enter else None,
        opacity=0.35 if enter else 1,
        scale=0.88 if enter else 1,
    )
    moved: Dict[str, float] = {"x": 0.0}

    def refresh() -> None:
        try:
            body.update()
        except RuntimeError:  # not on a page (yet, or any more): nothing to redraw
            pass

    def pose(fraction: float) -> None:
        body.offset = ft.Offset(fraction, 0)
        body.opacity = 1 - min(abs(fraction), 0.5) * 1.2
        body.scale = 1 - min(abs(fraction), 0.5) * 0.24
        refresh()

    def dragged(event: Any) -> None:
        moved["x"] += float(getattr(event, "primary_delta", None) or getattr(getattr(event, "local_delta", None), "x", 0) or 0)
        pose(max(-0.5, min(0.5, moved["x"] / 400)))

    def released(event: Any) -> None:
        dx, moved["x"] = moved["x"], 0.0
        if dx <= -SWIPE_DISTANCE or dx >= SWIPE_DISTANCE:
            delta = 1 if dx < 0 else -1
            if ctx is not None:
                ctx.memory[ENTER_KEY] = delta
            step(delta)
        else:
            pose(0)

    pages = ft.GestureDetector(content=body, on_horizontal_drag_update=dragged, on_horizontal_drag_end=released, expand=True)
    if enter and ctx is not None and getattr(ctx, "page", None) is not None:

        async def settle() -> None:
            await asyncio.sleep(0.03)
            body.offset, body.opacity, body.scale = ft.Offset(0, 0), 1, 1
            refresh()

        ctx.page.run_task(settle)
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
