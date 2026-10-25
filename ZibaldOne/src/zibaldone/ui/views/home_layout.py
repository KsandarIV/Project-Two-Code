"""Impostazioni · La tua home (0.2.8): which tiles Oggi shows, and in what order."""

from typing import Any, Callable, Dict, List

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


def build(ctx: AppContext) -> ft.Control:
    part = settings_part("home")
    with ctx.store() as store:
        view_names = {item.id: item.name for item in V.load_views(store)} if store.find_template(V.TEMPLATE) is not None else {}
    shown = [key for key in home_log.load_layout(ctx.folder) if not key.startswith("vista:") or key.split(":", 1)[1] in view_names]
    offered = list(home.TILES) + [f"vista:{view_id}" for view_id in view_names]
    hidden = [key for key in offered if key not in shown]

    def save(tiles: List[str]) -> None:
        home_log.save_layout(ctx.folder, tiles)
        ctx.refresh()

    def reorder(event: Any) -> None:
        tiles = list(shown)
        tiles.insert(event.new_index, tiles.pop(event.old_index))
        save(tiles)

    def switch(key: str, visible: bool) -> ft.Switch:
        def changed(event: Any) -> None:
            save(shown + [key] if event.control.value else [item for item in shown if item != key])

        return ft.Switch(value=visible, on_change=changed, active_color=T.ACCENT, disabled=visible and len(shown) == 1, tooltip="Mostra in Oggi" if not visible else "Nascondi da Oggi")

    def reset() -> None:
        home_log.reset_layout(ctx.folder)
        ctx.toast("La home è tornata com'era all'inizio.")
        ctx.refresh()

    def row(key: str, visible: bool) -> ft.Control:
        return ft.Container(
            ft.Row([W.body(label_of(key, view_names), expand=True, dim=not visible), switch(key, visible)], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.Padding.symmetric(horizontal=12, vertical=4),
            bgcolor=T.PANEL,
            border_radius=T.RADIUS_SMALL,
            key=key,
        )

    order = ft.ReorderableListView([row(key, True) for key in shown], on_reorder=reorder, show_default_drag_handles=True, item_extent=52)
    order.height = 52 * len(shown)
    controls: List[ft.Control] = [
        W.screen_header(part.nickname, part.label, part.description, on_back=ctx.back),
        W.caption("«I tre momenti» e «Le voci di oggi» restano sempre. Tieni premuto il quadratino di un riquadro e trascinalo per cambiarne l'ordine."),
        order,
    ]
    if hidden:
        controls.append(W.section_label("Nascosti"))
        controls.append(W.panel(ft.Column([ft.Row([W.body(label_of(key, view_names), dim=True, expand=True), switch(key, False)]) for key in hidden], spacing=2)))
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
