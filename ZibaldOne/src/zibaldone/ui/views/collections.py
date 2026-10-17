"""Collezioni · Museion: books, films, series … as cards with progress and stars."""

from typing import Any, List

import flet as ft

from zibaldone.ui import theme as T
from zibaldone.ui import viewmodels as vm
from zibaldone.ui import widgets as W
from zibaldone.ui.context import AppContext
from zibaldone.ui.navigation import Route, section


def build(ctx: AppContext, route: Route) -> ft.Control:
    info = section("collezioni")
    with ctx.store() as store:
        groups = vm.build_collections(store)
    controls: List[ft.Control] = [W.screen_header(info.label, info.nickname, "libri, film, serie e tutto ciò che raccogli")]
    if not groups:
        controls.append(
            W.empty_state(
                "Non hai ancora modelli di collezione. La Scuola «Museion · Collezioni» ne ha nove: libri, film, serie, anime, videogiochi e altri.",
                "COLLECTIONS_BOOKMARK_OUTLINED",
                W.primary_button("Vai alle Scuole", lambda _: ctx.go("/scuole"), icon="SCHOOL_OUTLINED"),
            )
        )
        return W.screen(controls, ctx.wide)
    filled = [group for group in groups if group.items]
    empty = [group for group in groups if not group.items]
    for group in filled:
        controls.append(_group(ctx, group))
    if empty:
        chips = [
            ft.Container(
                ft.Row([W.template_badge(group.icon, group.color, 28), W.body(group.name, size=13)], spacing=8, tight=True),
                padding=ft.Padding.only(left=4, right=12, top=4, bottom=4),
                border=ft.Border.all(1, T.BORDER),
                border_radius=T.RADIUS_SMALL,
                on_click=lambda _, slug=group.slug: ctx.go(f"/scrivi/{slug}"),
                ink=True,
                tooltip=group.description or None,
            )
            for group in empty
        ]
        controls.append(W.section_label("Raccolte ancora vuote"))
        controls.append(W.panel(ft.Column([W.caption("Tocca una raccolta per aggiungere la prima voce."), ft.Row(chips, wrap=True, spacing=8, run_spacing=8)], spacing=10)))
    return W.screen(controls, ctx.wide)


def _group(ctx: AppContext, group: vm.CollectionGroup) -> ft.Control:
    header = ft.Row(
        [
            W.template_badge(group.icon, group.color),
            ft.Column([W.h2(group.name), W.caption(group.count_label)], spacing=0, expand=True),
            W.secondary_button("Aggiungi", lambda _: ctx.go(f"/scrivi/{group.slug}"), icon="ADD"),
        ],
        spacing=12,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )
    cards = [_item(ctx, group, item) for item in group.items]
    return W.panel(ft.Column([header, ft.ResponsiveRow(cards, spacing=10, run_spacing=10)], spacing=14))


def _item(ctx: AppContext, group: vm.CollectionGroup, item: vm.CollectionItem) -> ft.Control:
    lines: List[ft.Control] = [ft.Text(item.title, size=15, weight=ft.FontWeight.W_600, color=T.TEXT, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS)]
    if item.subtitle:
        lines.append(W.caption(item.subtitle))
    if item.rating is not None:
        lines.append(W.stars(item.rating, item.rating_max, size=16))
    if item.status_label:
        lines.append(W.labelled_meter(item.status_label, item.fraction, item.counter, group.color))
    if item.bookmark:
        lines.append(ft.Row([ft.Icon(ft.Icons.BOOKMARK_BORDER, size=14, color=T.TEXT_DIM), W.caption(item.bookmark)], spacing=4))
    return W.panel(
        ft.Column(lines, spacing=8),
        padding=14,
        bgcolor=T.BG,
        on_click=lambda _: ctx.go(f"/voci/{item.id}"),
        col={"xs": 12, "md": 6, "xl": 4},
    )
