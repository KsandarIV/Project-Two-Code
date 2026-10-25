"""Impostazioni · La tua home (0.2.8): which tiles Oggi shows, and in what order."""

from typing import Any, Callable, Dict, List, Optional, Tuple

import flet as ft

from zibaldone.core import home
from zibaldone.storage import home_log
from zibaldone.ui import services
from zibaldone.core import views as V
from zibaldone.ui import theme as T
from zibaldone.ui import widgets as W
from zibaldone.ui.context import AppContext
from zibaldone.ui.navigation import settings_part

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

HINTS: Dict[str, str] = {
    "promemoria": "Il promemoria per scrivere, quando è ora.",
    "citazione": "Una frase dei filosofi, una al giorno.",
    "stoa": "Mattina, metà giornata e sera.",
    "aree": "Come vanno le otto aree della tua vita.",
    "abitudini": "I rituali di oggi, con la serie di giorni.",
    "ricorrenze": "Compleanni e date da non scordare.",
    "obiettivi": "A che punto sono i tuoi obiettivi.",
    "bilancio": "Entrate e uscite del mese.",
}


def label_of(key: str, view_names: Dict[str, str]) -> str:
    if key.startswith("vista:"):
        return f"Vista: {view_names.get(key.split(':', 1)[1], 'non più disponibile')}"
    return LABELS.get(key, key)


GROUP = "home"


def arrange(entries: List[Tuple[str, ft.Control]], view_names: Dict[str, str], save: Callable[[List[str]], None], remove: Optional[Callable[[str], None]] = None) -> ft.Control:
    """The blocks as they look, each under a handle: drag the handle onto another block to put it there.

    `entries` are (key, block) in order; `save` gets the new order of keys; `remove` (when given) adds a «take away» button to every block that is not fixed.
    """
    keys = [key for key, _ in entries]

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
        feedback = ft.Container(W.body(label_of(key, view_names), size=13), padding=10, bgcolor=T.PANEL, border_radius=T.RADIUS_SMALL, opacity=0.9)
        return ft.Draggable(group=GROUP, data=key, content=grip, content_feedback=feedback, content_when_dragging=ft.Container(grip, opacity=0.3))

    return ft.Column(
        [ft.DragTarget(group=GROUP, on_accept=dropped(key), content=ft.Column([handle(key), block], spacing=6), data=key) for key, block in entries],
        spacing=14,
    )


def build(ctx: AppContext) -> ft.Control:
    part = settings_part("home")
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

    def block(key: str) -> ft.Control:
        hint = HINTS.get(key, "Una ricerca salvata con Lente.")
        return W.panel(W.caption(hint), padding=12)

    order = arrange([(key, block(key)) for key in shown], view_names, save)
    controls: List[ft.Control] = [
        W.screen_header(part.nickname, part.label, part.description, on_back=ctx.back),
        W.section_label("Anteprima"),
        W.caption("Così è la tua home. Trascina la maniglia di un riquadro su un altro per spostarlo. «Le voci di oggi» restano sempre in fondo."),
        order,
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
    return W.screen(controls, ctx.wide)
