"""Agorà (0.2.1): everything about one person ("tutto di Marco"), area by area."""

from typing import Any, List

import flet as ft

from zibaldone.core.people import QUICK_KINDS, PeopleError
from zibaldone.storage.database import StoreError
from zibaldone.ui import theme as T
from zibaldone.ui import viewmodels as vm
from zibaldone.ui import widgets as W
from zibaldone.ui.context import AppContext
from zibaldone.ui.navigation import Route
from zibaldone.ui.views.common import not_found

QUICK_ICONS = {"Chiamata": "CALL", "Messaggi": "CHAT", "Di persona": "PEOPLE"}


def build_person(ctx: AppContext, route: Route) -> ft.Control:
    with ctx.store() as store:
        view = vm.person_view(store, route.arg, ctx.now().date())
    if view is None:
        return not_found(ctx, "Questa persona non c'è più, o non è una persona.")
    actions = [W.secondary_button("Modifica", lambda _: ctx.go(f"/voci/{view.id}/modifica"), icon="EDIT")]
    subtitle = " · ".join(part for part in (view.roles, view.nicknames and f"detto {view.nicknames}") if part)
    controls: List[ft.Control] = [W.screen_header(view.name, "Agorà", subtitle, on_back=ctx.back, actions=actions)]
    if view.areas:
        controls.append(
            ft.Row([ft.Container(W.pill(label, color), on_click=lambda _, key=key: ctx.go(f"/aree/{key}")) for key, label, color in view.areas], wrap=True, spacing=6)
        )
    if view.details:
        rows = []
        for label, value, url in view.details:
            text: ft.Control = W.text_button(value, lambda _, url=url: ctx.open_url(url)) if url else W.body(value)
            rows.append(ft.Row([ft.Container(W.caption(label), width=96), text], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER))
        controls.append(W.panel(ft.Column(rows, spacing=4)))
    controls.append(_contacts(ctx, view))
    for group in view.groups:
        tiles: List[ft.Control] = [W.body(f"{group.label} ({len(group.rows)})", size=16, weight=ft.FontWeight.W_600)]
        tiles += [_tile(ctx, row) for row in group.rows]
        controls.append(W.panel(ft.Column(tiles, spacing=10), border_color=W.fade(group.color, 0.45)))
    if view.mentions:
        tiles = [W.body("La nominano senza collegamento", size=16, weight=ft.FontWeight.W_600)]
        tiles += [_tile(ctx, row) for row in view.mentions]
        controls.append(W.panel(ft.Column(tiles, spacing=10)))
    if not view.groups and not view.mentions:
        controls.append(W.caption(f"Ancora nessuna voce collega {view.name}. Scrivi [[{view.name}]] in un testo, o segna un incontro."))
    return W.screen(controls, ctx.wide)


def _tile(ctx: AppContext, row: vm.EntryRow) -> ft.Control:
    return W.entry_tile(row.title, f"{row.template_name} · {row.day_label}", row.summary, row.icon, row.color, lambda _, entry_id=row.id: ctx.go(f"/voci/{entry_id}"))


def _contacts(ctx: AppContext, view: vm.PersonView) -> ft.Control:
    head: List[ft.Control] = [W.body("Contatti", size=16, weight=ft.FontWeight.W_600), ft.Container(expand=True)]
    if view.due:
        head.append(W.pill("da sentire", T.ACCENT_2, icon="WAVING_HAND"))
    rows: List[ft.Control] = [ft.Row(head, vertical_alignment=ft.CrossAxisAlignment.CENTER), W.caption(view.contact)]
    if view.rhythm:
        rows.append(W.caption(view.rhythm))
    if view.can_log:
        rows.append(
            ft.Row(
                [W.secondary_button(kind, lambda _, kind=kind: _log(ctx, view, kind), icon=QUICK_ICONS[kind]) for kind in QUICK_KINDS],
                wrap=True,
                spacing=8,
            )
        )
    for contact in view.contacts:
        rows.append(
            ft.Container(
                ft.Row(
                    [
                        ft.Icon(W.icon_of(contact.icon), size=18, color=T.ACCENT),
                        ft.Column([W.body(contact.title, size=14), W.caption(" · ".join(part for part in (contact.label, contact.day_label, contact.note) if part))], spacing=0, expand=True),
                    ],
                    spacing=10,
                ),
                on_click=lambda _, entry_id=contact.entry_id: ctx.go(f"/voci/{entry_id}"),
            )
        )
    return W.panel(ft.Column(rows, spacing=8))


def _log(ctx: AppContext, view: vm.PersonView, kind: str) -> None:
    try:
        with ctx.store() as store:
            entry = vm.log_person_contact(store, view.id, kind)
    except (PeopleError, StoreError, ValueError) as problem:
        ctx.toast(str(problem), error=True)
        return
    ctx.data_changed()
    ctx.toast(f"Segnato: {entry.values.get('titolo')}.", action="Racconta", on_action=lambda: ctx.go(f"/voci/{entry.id}/modifica"))
    ctx.refresh()
