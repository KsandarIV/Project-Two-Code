"""Kosmesis · Oikos (0.2.8, moved here in 0.3.3): which tiles Oggi shows, and in what order."""

import asyncio
from typing import Any, Callable, Dict, List, Optional, Tuple

import flet as ft

from zibaldone.core import home
from zibaldone.storage import home_log
from zibaldone.ui import services
from zibaldone.core import views as V
from zibaldone.ui import theme as T
from zibaldone.ui import widgets as W
from zibaldone.ui.context import AppContext

LABELS: Dict[str, str] = {
    "promemoria": "Promemoria",
    "citazione": "Pensiero del giorno",
    "stoa": "I tre momenti",
    "aree": "Le otto aree",
    "abitudini": "Abitudini di oggi",
    "ricorrenze": "Ricorrenze",
    "obiettivi": "Obiettivi",
    "bilancio": "Bilancio",
}

def label_of(key: str, view_names: Dict[str, str]) -> str:
    if key.startswith("vista:"):
        return f"Vista: {view_names.get(key.split(':', 1)[1], 'non più disponibile')}"
    return LABELS.get(key, key)


GROUP = "home"


HOLD_SECONDS = 0.8  # holding a dragged block this long brings out the crescent on the right
DRAG_TIMEOUT = 8  # Flet does not tell a cancelled drag: after this the dimmed block and the crescent are put back
CRESCENT = "crescent"  # key in ctx.memory of the crescent shown on the page overlay


def _drop_crescent(ctx: AppContext) -> None:
    crescent = ctx.memory.pop(CRESCENT, None)
    if crescent is not None and ctx.page is not None and crescent in ctx.page.overlay:
        ctx.page.overlay.remove(crescent)
        ctx.update()


def arrange(
    ctx: AppContext,
    entries: List[Tuple[str, ft.Control]],
    view_names: Dict[str, str],
    save: Callable[[List[str]], None],
    remove: Optional[Callable[[str], None]] = None,
    off: Optional[List[str]] = None,
) -> ft.Control:
    """The blocks as they look: drag a whole block onto another to put it there.

    `entries` are (key, block) in order; `save` gets the new order of keys; `remove` (when given) adds a «take away» button to every block that is not fixed.
    With `off` (the keys switched off) a zone «Spenti» shows them faded: drag a block in to switch it off, out to switch it on. Holding a dragged block for a moment
    brings out a crescent on the right, so a far zone can be reached without scrolling; dropping on it switches the block off.
    """
    keys = [key for key, _ in entries]
    blocks = dict(entries)
    _drop_crescent(ctx)  # a redraw: the old crescent is stale
    dragging = {"id": 0, "boxes": {}}

    def settle() -> None:
        dragging["id"] += 1  # the timers of the drag that just ended stop here
        _drop_crescent(ctx)
        for box in dragging["boxes"].values():
            box.opacity = 1
            ctx.update(box)

    def place(moving: str, order: List[str]) -> None:
        settle()
        save(order)

    def dropped(target: str) -> Callable[[Any], None]:
        def accept(event: Any) -> None:
            moving = getattr(event.src, "data", None)
            if moving is None or moving == target or moving not in keys + (off or []):
                return
            order = [key for key in keys if key != moving]
            order.insert(order.index(target) if target in order else len(order), moving)
            place(moving, order)

        return accept

    def switched_off(event: Any) -> None:
        moving = getattr(event.src, "data", None)
        if moving in keys and len(keys) > 1:  # Oggi never stays empty
            place(moving, [key for key in keys if key != moving])
        else:
            settle()

    def show_crescent() -> None:
        height = float(getattr(ctx.page, "height", None) or 600)
        crescent = ft.Container(
            ft.DragTarget(
                group=GROUP,
                on_accept=switched_off,
                content=ft.Container(
                    ft.Icon(W.icon_of("VISIBILITY_OFF_OUTLINED"), size=26, color=T.TEXT),
                    width=64,
                    height=160,
                    bgcolor=W.fade(T.ACCENT, 0.45),
                    border_radius=ft.BorderRadius.only(top_left=80, bottom_left=80),
                    alignment=ft.Alignment.CENTER,
                    tooltip="Lascialo qui per spegnerlo",
                ),
            ),
            right=0,
            top=max(height / 2 - 80, 0),
        )
        ctx.memory[CRESCENT] = crescent
        ctx.page.overlay.append(crescent)
        ctx.update()

    def lifted(box: ft.Control) -> Callable[[Any], None]:
        def start(_: Any) -> None:
            box.opacity = 0.3  # the block turns see-through while it moves
            ctx.update(box)
            if off is None or ctx.page is None or not hasattr(ctx.page, "run_task"):
                return
            dragging["id"] += 1
            mine = dragging["id"]

            async def hold() -> None:
                await asyncio.sleep(HOLD_SECONDS)
                if dragging["id"] == mine:
                    show_crescent()
                await asyncio.sleep(DRAG_TIMEOUT)
                if dragging["id"] == mine:
                    settle()

            ctx.page.run_task(hold)

        return start

    def card(key: str, faded: bool) -> ft.Control:
        label = ft.Row(
            [ft.Icon(W.icon_of("DRAG_INDICATOR"), size=20, color=T.TEXT_DIM), W.body(label_of(key, view_names), size=13, expand=True)]
            + ([W.icon_button("CLOSE", lambda _, key=key: remove(key), "Togli da Oggi", color=T.TEXT_DIM)] if remove is not None and key not in home.FIXED and not faded else []),
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        grip = ft.Container(label, padding=ft.Padding.symmetric(horizontal=10, vertical=2), bgcolor=T.PANEL, border_radius=T.RADIUS_SMALL)
        box = ft.Container(blocks[key], animate_opacity=150) if not faded else ft.Container(opacity=0.45)
        dragging["boxes"][key] = box
        whole = ft.Column([grip] + ([box] if not faded else []), spacing=6)
        feedback = ft.Container(W.body(label_of(key, view_names), size=13), padding=10, bgcolor=T.PANEL, border_radius=T.RADIUS_SMALL, opacity=0.6)
        return ft.Draggable(group=GROUP, data=key, content=whole, content_feedback=feedback, on_drag_start=lifted(box) if not faded else None)

    active = ft.Column(
        [ft.DragTarget(group=GROUP, on_accept=dropped(key), content=card(key, False), data=key) for key in keys]
        + [ft.DragTarget(group=GROUP, on_accept=dropped("__end__"), content=ft.Container(height=24), data="__end__")],  # the end of the list
        spacing=14,
    )
    if off is None:
        return active
    zone = ft.DragTarget(
        group=GROUP,
        on_accept=switched_off,
        content=W.panel(
            ft.Column([card(key, True) for key in off] or [W.caption("Trascina qui un blocco per spegnerlo; da qui lo riporti nella home.")], spacing=8),
            border_color=W.fade(T.TEXT_DIM, 0.5),
        ),
    )
    return ft.Column([active, W.section_label("Spenti"), zone], spacing=14)


def build(ctx: AppContext) -> List[ft.Control]:
    """The Oikos section of Kosmesis: the controls to put under its title."""
    with ctx.store() as store:
        view_names = {item.id: item.name for item in V.load_views(store)} if store.find_template(V.TEMPLATE) is not None else {}
    shown = [key for key in home_log.load_layout(ctx.folder) if not key.startswith("vista:") or key.split(":", 1)[1] in view_names]
    offered = list(home.TILES) + [f"vista:{view_id}" for view_id in view_names]

    def save(tiles: List[str]) -> None:
        home_log.save_layout(ctx.folder, tiles)
        ctx.refresh()

    def switch(key: str, visible: bool) -> ft.Switch:
        def changed(event: Any) -> None:
            save(shown + [key] if event.control.value else [item for item in shown if item != key])

        return ft.Switch(value=visible, on_change=changed, active_color=T.ACCENT, disabled=visible and len(shown) == 1, tooltip="Mostra in Oggi" if not visible else "Nascondi da Oggi")

    def reset() -> None:
        home_log.reset_layout(ctx.folder)
        ctx.toast("La home è tornata com'era all'inizio.")
        ctx.refresh()

    from zibaldone.ui.views import today  # here, not on top: Oggi imports this module

    entries, _ = today.preview_entries(ctx)
    controls: List[ft.Control] = [
        W.caption("Così è la tua home, con i riquadri veri. Trascina un riquadro su un altro per spostarlo; in fondo, nei «Spenti», quelli che non vuoi vedere. «Le voci di oggi» restano sempre in fondo."),
        arrange(ctx, entries, view_names, save, off=[key for key in offered if key not in shown]),
        W.section_label("Accendi e spegni"),
        W.panel(ft.Column([ft.Row([W.body(label_of(key, view_names), dim=key not in shown, expand=True), switch(key, key in shown)]) for key in offered], spacing=2)),
    ]
    pinned = services.shortcuts(ctx.folder)
    with ctx.store() as store:
        names = {slug: store.find_template(slug) for slug in pinned}
    controls.append(W.section_label("Scorciatoie ai modelli"))
    pinned_rows = [
        ft.Row(
            [W.body(names[slug].name, expand=True), W.text_button("Togli", lambda _, slug=slug: (services.toggle_shortcut(ctx.folder, slug), ctx.refresh()), icon="PUSH_PIN")]
        )
        for slug in pinned
        if names[slug] is not None
    ]
    controls.append(W.panel(ft.Column(pinned_rows or [W.caption("Nessuna. Da Modelli, la puntina mette un modello in Oggi: un tocco e scrivi.")], spacing=2)))
    controls.append(
        ft.Row(
            [W.secondary_button("Ripristina", lambda _: ctx.confirm("Ripristinare la home?", "I riquadri tornano tutti visibili, nell'ordine di partenza.", "Ripristina", reset, danger=False), icon="RESTART_ALT")],
            alignment=ft.MainAxisAlignment.END,
        )
    )
    return controls
