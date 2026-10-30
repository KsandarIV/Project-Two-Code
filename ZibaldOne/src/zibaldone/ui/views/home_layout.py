"""Kosmesis · Oikos (0.2.8, moved here in 0.3.3): which tiles Oggi shows, and in what order."""

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


def arrange(entries: List[Tuple[str, ft.Control]], view_names: Dict[str, str], save: Callable[[List[str]], None], remove: Optional[Callable[[str], None]] = None) -> ft.Control:
    """The blocks as they look, each under a handle: drag it onto another block to put it there.

    The block fades while its handle is dragged; only the handle moves, so the page still scrolls on a phone.

    `entries` are (key, block) in order; `save` gets the new order of keys; `remove` (when given) adds a «take away» button to every block that is not fixed.
    """
    keys = [key for key, _ in entries]
    blocks = dict(entries)

    def dropped(target: str) -> Callable[[Any], None]:
        def accept(event: Any) -> None:
            moving = getattr(event.src, "data", None)
            if moving not in keys or moving == target:
                return
            order = [key for key in keys if key != moving]
            order.insert(order.index(target), moving)
            save(order)

        return accept

    def handle(key: str) -> ft.Control:
        label = ft.Row(
            [ft.Icon(W.icon_of("DRAG_INDICATOR"), size=20, color=T.TEXT_DIM), W.body(label_of(key, view_names), size=13, expand=True)]
            + ([W.icon_button("CLOSE", lambda _, key=key: remove(key), "Togli da Oggi", color=T.TEXT_DIM)] if remove is not None and key not in home.FIXED else []),
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        grip = ft.Container(label, padding=ft.Padding.symmetric(horizontal=10, vertical=2), bgcolor=T.PANEL, border_radius=T.RADIUS_SMALL)
        box = ft.Container(blocks[key], animate_opacity=150)

        def lifted(_: Any) -> None:  # the block turns see-through while its handle moves
            box.opacity = 0.3
            box.update()

        feedback = ft.Container(W.body(label_of(key, view_names), size=13), padding=10, bgcolor=T.PANEL, border_radius=T.RADIUS_SMALL, opacity=0.6)
        drag = ft.Draggable(group=GROUP, data=key, content=grip, content_feedback=feedback, content_when_dragging=ft.Container(height=34), on_drag_start=lifted)
        return ft.Column([drag, box], spacing=6)

    return ft.Column(
        [ft.DragTarget(group=GROUP, on_accept=dropped(key), content=handle(key), data=key) for key in keys],
        spacing=14,
    )


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
        W.caption("Così è la tua home, con i riquadri veri. Trascina la maniglia di un riquadro su un altro per spostarlo. «Le voci di oggi» restano sempre in fondo."),
        arrange(entries, view_names, save),
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
