"""The «Novità» button: a star with a few sparkles that twinkle at random, gently.

While there is something unseen the star glows and the sparkles are brighter; after that only the sparkles are left, dimmer.
"""

import asyncio
import random
from typing import Any, Callable, List, Optional

import flet as ft

from zibaldone.ui import theme as T
from zibaldone.ui import widgets as W

SIZE = 44
SPOTS = ((2, 4), (30, 0), (34, 26), (0, 28))  # where the four sparkles sit, in the box
STEP_SECONDS = 0.9


def _level(unseen: bool, wide: bool) -> float:
    """How bright a sparkle gets at most: the calmer, the lower."""
    base = 0.9 if unseen else 0.45
    return base * (0.6 if wide else 1.0)


def sparkle_button(on_click: Callable[[Any], None], unseen: bool, wide: bool) -> ft.Stack:
    """The button; `twinkle` can be run on its `data` list of sparkles."""
    star = ft.Container(
        ft.Icon(W.icon_of("AUTO_AWESOME"), size=22, color=T.ACCENT if unseen else T.TEXT_DIM),
        width=SIZE - 10,
        height=SIZE - 10,
        left=5,
        top=5,
        alignment=ft.Alignment.CENTER,
        border_radius=SIZE,
        bgcolor=W.fade(T.ACCENT, 0.16) if unseen else None,
        border=ft.Border.all(1, T.ACCENT) if unseen else None,
        shadow=ft.BoxShadow(blur_radius=14, color=W.fade(T.ACCENT, 0.5)) if unseen else None,
        tooltip="Novità",
        on_click=on_click,
        ink=True,
    )
    sparks = [
        ft.Container(ft.Icon(W.icon_of("STAR"), size=8, color=T.ACCENT), left=x, top=y, opacity=0.0, animate_opacity=ft.Animation(700, ft.AnimationCurve.EASE_IN_OUT))
        for x, y in SPOTS
    ]
    box = ft.Stack([star, *sparks], width=SIZE, height=SIZE)
    box.data = {"sparks": sparks, "level": _level(unseen, wide)}
    return box


def _mounted(box: ft.Control) -> bool:
    try:
        return box.page is not None
    except RuntimeError:  # not on a page (yet, or any more)
        return False


async def twinkle(page: Any, box: ft.Stack, rng: Optional[random.Random] = None) -> None:
    """Light one random sparkle at a time until the button leaves the page."""
    rng = rng or random.Random()
    sparks: List[ft.Container] = box.data["sparks"]
    level: float = box.data["level"]
    await asyncio.sleep(0.3)  # let the screen mount first
    while _mounted(box):
        spark = rng.choice(sparks)
        spark.opacity = level * rng.uniform(0.5, 1.0)
        try:
            spark.update()
            await asyncio.sleep(STEP_SECONDS * rng.uniform(0.6, 1.4))
            spark.opacity = 0.0
            spark.update()
        except Exception:  # the screen changed under us
            return
        await asyncio.sleep(STEP_SECONDS * rng.uniform(0.2, 0.8))
