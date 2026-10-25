"""Collezioni · Museion: books, films, series … as cards with progress and stars."""

from typing import Any, List

import flet as ft

from zibaldone.ui import carousel
from zibaldone.ui import theme as T
from zibaldone.ui import viewmodels as vm
from zibaldone.ui import widgets as W
from zibaldone.ui.context import AppContext
from zibaldone.ui.navigation import Route, section
from zibaldone.ui.views.common import not_found
from zibaldone.ui.views.import_dialog import open_import

ALL = ""  # the first page: every collection as cards


def build(ctx: AppContext, route: Route) -> ft.Control:
    info = section("collezioni")
    with ctx.store() as store:
        groups = vm.build_collections(store)
    import_button = W.secondary_button("Importa da un file", lambda _: open_import(ctx, ctx.refresh), icon="DOWNLOAD")
    controls: List[ft.Control] = [W.screen_header(info.label, info.nickname, "libri, film, serie e tutto ciò che raccogli", actions=[import_button])]
    if not groups:
        controls.append(
            W.empty_state(
                "Non hai ancora modelli di collezione. La Scuola «Museion · Collezioni» ne ha nove: libri, film, serie, anime, videogiochi e altri.",
                "COLLECTIONS_BOOKMARK_OUTLINED",
                W.primary_button("Vai alle Scuole", lambda _: ctx.go("/scuole"), icon="SCHOOL_OUTLINED"),
            )
        )
        return W.screen(controls, ctx.wide)
    pages = carousel.centered(ALL, [group.slug for group in groups])
    page = ctx.memory.get("collezioni_pagina", ALL)
    if page not in pages:
        page = ALL

    def choose(target: str) -> None:
        ctx.memory["collezioni_pagina"] = target
        ctx.refresh()

    ctx.back_hook = carousel.hook_back(ctx, ALL, page, lambda: choose(ALL))
    bar = [carousel.bar_item(ft.Icon(W.icon_of("COLLECTIONS_BOOKMARK_OUTLINED"), size=24, color=T.ACCENT), T.ACCENT, "Tutte", page == ALL, lambda: choose(ALL))]
    bar += [carousel.bar_item(ft.Icon(W.icon_of(group.icon), size=24, color=group.color), group.color, group.name, group.slug == page, lambda target=group.slug: choose(target)) for group in groups]
    shown = next((group for group in groups if group.slug == page), None)
    if shown is not None:
        controls[0] = W.screen_header(shown.name, "Museion", shown.description or shown.count_label, actions=[W.primary_button("Aggiungi", lambda _: ctx.go(f"/scrivi/{shown.slug}"), icon="ADD"), import_button])
        controls += _group_items(ctx, shown)
    else:
        controls += _overview(ctx, groups)
        controls.append(W.section_label("Le raccolte"))
        controls.append(ft.ResponsiveRow([_card(ctx, group) for group in groups], spacing=12, run_spacing=12))
    color = shown.color if shown is not None else T.ACCENT
    return carousel.page_body(W.screen(controls, ctx.wide), bar, color, lambda delta: choose(carousel.next_page(pages, page, delta)), ctx)


def _card(ctx: AppContext, group: vm.CollectionGroup) -> ft.Control:
    """One collection: its page opens on a tap (the items are on the child page, not here)."""
    return W.panel(
        ft.Row(
            [
                W.template_badge(group.icon, group.color),
                ft.Column([W.body(group.name, size=16, weight=ft.FontWeight.W_600), W.caption(group.count_label)], spacing=0, expand=True),
                ft.Icon(ft.Icons.CHEVRON_RIGHT, color=T.TEXT_DIM, size=20),
            ],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding.symmetric(horizontal=14, vertical=12),
        on_click=lambda _: ctx.go(f"/collezioni/{group.slug}"),
        col={"xs": 12, "md": 6, "xl": 4},
    )


def build_group(ctx: AppContext, route: Route) -> ft.Control:
    """The child page of one collection: its items, and «Aggiungi»."""
    with ctx.store() as store:
        group = next((item for item in vm.build_collections(store) if item.slug == route.arg), None)
    if group is None:
        return not_found(ctx, "Questa raccolta non esiste. Le raccolte sono i modelli della Scuola «Museion · Collezioni».")
    add = W.primary_button("Aggiungi", lambda _: ctx.go(f"/scrivi/{group.slug}"), icon="ADD")
    controls: List[ft.Control] = [W.screen_header(group.name, "Museion", group.description or group.count_label, on_back=ctx.back, actions=[add])]
    controls += _group_items(ctx, group)
    return W.screen(controls, ctx.wide)


def _group_items(ctx: AppContext, group: vm.CollectionGroup) -> List[ft.Control]:
    if group.items:
        return [ft.ResponsiveRow([_item(ctx, group, item) for item in group.items], spacing=10, run_spacing=10)]
    return [W.empty_state("Questa raccolta è ancora vuota. Tocca «Aggiungi» per la prima voce.", group.icon)]


def _chip(ctx: AppContext, text: str, entry_id: str, icon: str = "", color: str = T.ACCENT_2) -> ft.Control:
    content: List[ft.Control] = ([ft.Icon(W.icon_of(icon), size=14, color=color)] if icon else []) + [W.body(text, size=13)]
    return ft.Container(
        ft.Row(content, spacing=6, tight=True),
        padding=ft.Padding.symmetric(horizontal=12, vertical=6),
        border=ft.Border.all(1, T.BORDER),
        border_radius=T.RADIUS_SMALL,
        on_click=lambda _: ctx.go(f"/voci/{entry_id}"),
        ink=True,
    )


def _overview(ctx: AppContext, groups: List[vm.CollectionGroup]) -> List[ft.Control]:
    """Favourites, the wish list and the time spent, across all the collections (0.2.5)."""
    panels: List[ft.Control] = []
    favorites, wishes = vm.favorites_of(groups), vm.wishlist_of(groups)
    if favorites:
        chips = [_chip(ctx, item.title, item.id, "FAVORITE") for _, item in favorites]
        panels.append(W.panel(ft.Column([W.section_label("Preferiti"), ft.Row(chips, wrap=True, spacing=8, run_spacing=8)], spacing=10)))
    if wishes:
        chips = [_chip(ctx, f"{item.title} · {group.name}", item.id, "BOOKMARK_BORDER", T.ACCENT) for group, item in wishes]
        panels.append(W.panel(ft.Column([W.section_label("Lista dei desideri"), ft.Row(chips, wrap=True, spacing=8, run_spacing=8)], spacing=10)))
    spent = [group for group in groups if group.hours > 0]
    if spent:
        rows = [ft.Row([W.body(group.name, expand=True), W.body(vm.hours_label(group.hours), dim=True)]) for group in sorted(spent, key=lambda group: -group.hours)]
        panels.append(W.panel(ft.Column([W.section_label("Tempo speso"), *rows], spacing=8)))
    return panels


def _item(ctx: AppContext, group: vm.CollectionGroup, item: vm.CollectionItem) -> ft.Control:
    title: ft.Control = ft.Text(item.title, size=15, weight=ft.FontWeight.W_600, color=T.TEXT, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS, expand=True)
    if item.favorite:
        title = ft.Row([title, ft.Icon(ft.Icons.FAVORITE, size=16, color=T.ACCENT_2)], spacing=6)
    lines: List[ft.Control] = [title]
    if item.subtitle:
        lines.append(W.caption(item.subtitle))
    if item.rating is not None:
        lines.append(W.stars(item.rating, item.rating_max, size=16))
    if item.status_label:
        lines.append(W.labelled_meter(item.status_label, item.fraction, item.counter, group.color))
    if item.bookmark:
        lines.append(ft.Row([ft.Icon(ft.Icons.BOOKMARK_BORDER, size=14, color=T.TEXT_DIM), W.caption(item.bookmark)], spacing=4))
    if item.hours > 0:
        lines.append(W.caption(vm.hours_label(item.hours)))
    return W.panel(
        ft.Column(lines, spacing=8),
        padding=14,
        bgcolor=T.BG,
        on_click=lambda _: ctx.go(f"/voci/{item.id}"),
        col={"xs": 12, "md": 6, "xl": 4},
    )
