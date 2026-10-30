"""Helpers shared by several views: date picker, template chooser, error screen."""

from datetime import date, datetime, time
from typing import Any, Callable, List, Optional

import flet as ft

from zibaldone.ui import theme as T
from zibaldone.ui import viewmodels as vm
from zibaldone.ui import widgets as W
from zibaldone.ui.context import AppContext


def pick_date(ctx: AppContext, current: str, on_pick: Callable[[date], Any], help_text: str = "Scegli il giorno") -> None:
    """Open the date picker on `current` (ISO or '') and call `on_pick` with the chosen day."""
    try:
        initial = date.fromisoformat(current) if current else ctx.now().date()
    except ValueError:
        initial = ctx.now().date()

    def changed(event: Any) -> None:
        chosen = vm.picked_date(event.control.value)
        if chosen is not None:
            on_pick(chosen)

    picker = ft.DatePicker(
        value=datetime.combine(initial, time(12)),
        first_date=datetime(1900, 1, 1),
        last_date=datetime(2100, 12, 31),
        current_date=ctx.now(),
        help_text=help_text,
        cancel_text="Annulla",
        confirm_text="OK",
        on_change=changed,
    )
    ctx.show_dialog(picker)


def choose_template(ctx: AppContext, title: str = "Nuova voce", category: Optional[str] = None) -> None:
    """A dialog listing the templates; picking one opens its form."""
    with ctx.store() as store:
        templates = store.list_templates(category=category)
        counts = {template.slug: store.count_entries(template.slug) for template in templates}
    groups = vm.group_templates(templates, counts)

    def open_form(slug: str) -> Callable[[Any], None]:
        def handler(_: Any) -> None:
            ctx.close_dialog()
            ctx.go(f"/scrivi/{slug}")

        return handler

    items: List[ft.Control] = []
    for label, rows in groups:
        items.append(W.section_label(label))
        for row in rows:
            items.append(
                ft.Container(
                    ft.Row(
                        [W.template_badge(row.icon, row.color, 32), ft.Column([W.body(row.name), W.caption(row.counts_label)], spacing=0, expand=True)],
                        spacing=10,
                    ),
                    padding=ft.Padding.symmetric(horizontal=8, vertical=6),
                    border_radius=T.RADIUS_SMALL,
                    on_click=open_form(row.slug),
                    ink=True,
                )
            )
    if not items:
        items.append(W.body("Non hai ancora modelli: installane qualcuno dalle Scuole.", dim=True))

    def to_packs(_: Any) -> None:
        ctx.close_dialog()
        ctx.go("/scuole")

    dialog = ft.AlertDialog(
        title=title,
        content=ft.Container(ft.Column(items, scroll=ft.ScrollMode.AUTO, spacing=2), width=420, height=460),
        actions=[W.text_button("Scuole", to_packs, color=T.TEXT_DIM), W.text_button("Chiudi", ctx.close_dialog)],
    )
    ctx.show_dialog(dialog)


def error_screen(ctx: AppContext, message: str) -> ft.Control:
    return W.screen(
        [
            W.screen_header("Qualcosa non va", on_back=ctx.back),
            W.panel(
                ft.Column(
                    [
                        W.body("Questa pagina non si è potuta aprire. I tuoi dati non sono stati toccati."),
                        W.body(message, dim=True, selectable=True),
                        W.secondary_button("Torna a Oikos home", lambda _: ctx.go("/oggi"), icon="TODAY"),
                    ],
                    spacing=10,
                ),
                border_color=W.fade(T.ERROR, 0.5),
            ),
        ],
        ctx.wide,
    )


def not_found(ctx: AppContext, text: str) -> ft.Control:
    return W.screen([W.screen_header("Non trovato", on_back=ctx.back), W.empty_state(text, "SEARCH")], ctx.wide)
