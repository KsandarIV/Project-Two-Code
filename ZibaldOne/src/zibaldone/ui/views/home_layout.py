"""Impostazioni · La tua home: the home is a grid (0.3.0); it is edited on Oggi itself, here is the way in, plus the shortcuts to models."""

from typing import List

import flet as ft

from zibaldone.storage import home_log
from zibaldone.ui import services
from zibaldone.ui import widgets as W
from zibaldone.ui.context import AppContext
from zibaldone.ui.navigation import settings_part
from zibaldone.ui.views.home_grid import set_editing


def build(ctx: AppContext) -> ft.Control:
    part = settings_part("home")

    def edit(_: object) -> None:
        set_editing(ctx, True)
        ctx.go("/oggi")

    def reset() -> None:
        home_log.reset_layout(ctx.folder)
        ctx.toast("La home è tornata com'era all'inizio.")
        ctx.refresh()

    controls: List[ft.Control] = [
        W.screen_header(part.nickname, part.label, part.description, on_back=ctx.back),
        W.panel(
            ft.Column(
                [
                    W.body("Oggi è una griglia di 5 colonne per 6 righe: ogni riquadro ha un posto e una grandezza."),
                    W.caption("«I tre momenti» e «Le voci di oggi» stanno sotto la griglia e restano sempre."),
                    ft.Row([W.primary_button("Modifica la home", edit, icon="DASHBOARD_CUSTOMIZE_OUTLINED")], alignment=ft.MainAxisAlignment.END),
                ],
                spacing=8,
            )
        ),
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
