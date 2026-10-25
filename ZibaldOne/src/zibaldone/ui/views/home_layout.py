"""Impostazioni · La tua home (0.2.8): which tiles Oggi shows, and in what order."""

from typing import Any, Callable, Dict, List

import flet as ft

from zibaldone.core import home
from zibaldone.storage import home_log
from zibaldone.ui import services
from zibaldone.core import views as V
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


def moved(tiles: List[str], index: int, step: int) -> List[str]:
    """`tiles` with the one at `index` moved by `step` places, kept inside the list."""
    target = index + step
    if not 0 <= target < len(tiles):
        return list(tiles)
    result = list(tiles)
    result[index], result[target] = result[target], result[index]
    return result


def build(ctx: AppContext) -> ft.Control:
    part = settings_part("home")
    with ctx.store() as store:
        view_names = {item.id: item.name for item in V.load_views(store)} if store.find_template(V.TEMPLATE) is not None else {}
    shown = [key for key in home_log.load_layout(ctx.folder) if not key.startswith("vista:") or key.split(":", 1)[1] in view_names]
    offered = list(home.TILES) + [f"vista:{view_id}" for view_id in view_names]
    hidden = [key for key in offered if key not in shown]

    def save(tiles: List[str]) -> Callable[[Any], None]:
        def run(_: Any) -> None:
            home_log.save_layout(ctx.folder, tiles)
            ctx.refresh()

        return run

    def reset() -> None:
        home_log.reset_layout(ctx.folder)
        ctx.toast("La home è tornata com'era all'inizio.")
        ctx.refresh()

    rows: List[ft.Control] = []
    for index, key in enumerate(shown):
        rows.append(
            ft.Row(
                [
                    W.body(label_of(key, view_names), expand=True),
                    W.icon_button("ARROW_UPWARD", save(moved(shown, index, -1)), tooltip="Sposta su", disabled=index == 0),
                    W.icon_button("ARROW_DOWNWARD", save(moved(shown, index, 1)), tooltip="Sposta giù", disabled=index == len(shown) - 1),
                    W.icon_button("VISIBILITY_OFF_OUTLINED", save([item for item in shown if item != key]), tooltip="Nascondi", disabled=len(shown) == 1),
                ],
                spacing=2,
            )
        )
    controls: List[ft.Control] = [
        W.screen_header(part.nickname, part.label, part.description, on_back=ctx.back),
        W.caption("«I tre momenti» e «Le voci di oggi» restano sempre."),
        W.panel(ft.Column(rows, spacing=2)),
    ]
    if hidden:
        controls.append(W.section_label("Nascosti"))
        controls.append(
            W.panel(
                ft.Column(
                    [ft.Row([W.body(label_of(key, view_names), dim=True, expand=True), W.text_button("Mostra", save(shown + [key]), icon="VISIBILITY_OUTLINED")]) for key in hidden],
                    spacing=2,
                )
            )
        )
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
