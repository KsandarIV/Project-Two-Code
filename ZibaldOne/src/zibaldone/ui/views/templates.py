"""Modelli · Forme: the templates by category, the built-in packs (Scuole) and the export."""

from typing import Any, Callable, Dict, List, Optional

import flet as ft

from zibaldone.core.areas import AREA_BY_KEY, AREA_LIST
from zibaldone.core.brand import NOMENCLATURE
from zibaldone.core.packs import apply_install, builtin_packs, plan_install
from zibaldone.storage.database import StoreError
from zibaldone.ui import services
from zibaldone.ui import theme as T
from zibaldone.ui import viewmodels as vm
from zibaldone.ui import widgets as W
from zibaldone.ui.context import AppContext
from zibaldone.ui.navigation import Route, section


GENERAL = ""  # the ninth page: templates with no area
SWIPE_DISTANCE = 60  # pixels of drag, after the long press, that change the page
AREA_TINT = 0.07


def _pages() -> List[str]:
    return [GENERAL] + [area.key for area in AREA_LIST]


def _page_color(page: str) -> str:
    return AREA_BY_KEY[page].color if page else T.ACCENT


def _page_label(page: str) -> str:
    return AREA_BY_KEY[page].label if page else "Generale"


def _template_tile(ctx: AppContext, row: vm.TemplateRow, pinned: Any, pin: Callable[[str], Callable[[Any], None]]) -> ft.Control:
    return W.panel(
        ft.Row(
            [
                W.template_badge(row.icon, row.color),
                ft.Column(
                    [
                        ft.Text(row.name, size=15, weight=ft.FontWeight.W_600, color=T.TEXT),
                        W.caption(row.counts_label),
                        ft.Text(row.description, size=12, color=T.TEXT_DIM, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS) if row.description else ft.Container(),
                    ],
                    spacing=2,
                    expand=True,
                ),
                W.icon_button("PUSH_PIN" if row.slug in pinned else "PUSH_PIN_OUTLINED", pin(row.slug), "Togli da Oggi" if row.slug in pinned else "Metti in Oggi", color=T.ACCENT if row.slug in pinned else T.TEXT_DIM),
                W.icon_button("TUNE", lambda _, slug=row.slug: ctx.go(f"/modelli/{slug}"), "Modifica il modello", color=T.TEXT_DIM),
            ],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding.symmetric(horizontal=14, vertical=12),
        on_click=lambda _, slug=row.slug: ctx.go(f"/scrivi/{slug}"),
        col={"xs": 12, "lg": 6},
    )


def _icon_tile(ctx: AppContext, row: vm.TemplateRow) -> ft.Control:
    return ft.Container(
        ft.Column([W.template_badge(row.icon, row.color, size=48), ft.Text(row.name, size=11, color=T.TEXT_DIM, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, text_align=ft.TextAlign.CENTER)], spacing=4, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        width=76,
        tooltip=row.name,
        on_click=lambda _, slug=row.slug: ctx.go(f"/scrivi/{slug}"),
        ink=True,
        border_radius=T.RADIUS_SMALL,
    )


def _page_bar(ctx: AppContext, page: str, choose: Callable[[str], None]) -> ft.Control:
    items: List[ft.Control] = []
    for key in _pages():
        color = _page_color(key)
        face = W.mascot_avatar(AREA_BY_KEY[key].mascot, 30) if key else ft.Icon(W.icon_of("DASHBOARD_OUTLINED"), size=24, color=T.ACCENT)
        items.append(
            ft.Container(
                face,
                padding=4,
                border_radius=T.RADIUS_SMALL,
                bgcolor=W.fade(color, 0.22) if key == page else None,
                border=ft.Border.all(1, color) if key == page else None,
                tooltip=_page_label(key),
                on_click=lambda _, target=key: choose(target),
                ink=True,
            )
        )
    return ft.Row(items, alignment=ft.MainAxisAlignment.SPACE_AROUND, spacing=2)


def build_list(ctx: AppContext, route: Route) -> ft.Control:
    info = section("modelli")
    page = ctx.memory.get("modelli_area", GENERAL)
    compact = ctx.memory.get("modelli_vista", "completa") == "icone"
    with ctx.store() as store:
        templates = store.list_templates()
        counts = {template.slug: store.count_entries(template.slug) for template in templates}
    groups = vm.group_templates(templates, counts, area=page)
    pinned = services.shortcuts(ctx.folder)

    def pin(slug: str) -> Callable[[Any], None]:
        def toggle(_: Any) -> None:
            ctx.toast("Aggiunto alle scorciatoie di Oggi." if services.toggle_shortcut(ctx.folder, slug) else "Tolto dalle scorciatoie di Oggi.")
            ctx.refresh()

        return toggle

    def choose(target: str) -> None:
        ctx.memory["modelli_area"] = target
        ctx.refresh()

    def step(delta: int) -> None:
        pages = _pages()
        choose(pages[(pages.index(page) + delta) % len(pages)])

    def toggle_view(_: Any) -> None:
        ctx.memory["modelli_vista"] = "completa" if compact else "icone"
        ctx.refresh()

    drag = {"dx": 0.0}

    def moved(event: Any) -> None:
        drag["dx"] = event.offset_from_origin.x

    def released(_: Any) -> None:
        dx, drag["dx"] = drag["dx"], 0.0
        if dx <= -SWIPE_DISTANCE:
            step(1)
        elif dx >= SWIPE_DISTANCE:
            step(-1)

    # Back from an area page goes to the general one before leaving Modelli.
    ctx.back_hook = (lambda: choose(GENERAL) or True) if page != GENERAL else None

    actions = [
        W.primary_button("Nuovo modello", lambda _: ctx.go("/modelli/nuovo"), icon="ADD"),
        W.secondary_button(f"{NOMENCLATURE['pack'].name} · pacchetti", lambda _: ctx.go("/scuole"), icon="SCHOOL_OUTLINED"),
        W.secondary_button("Esporta", lambda _: export_dialog(ctx), icon="DOWNLOAD", disabled=not templates),
        W.icon_button("GRID_VIEW" if compact else "VIEW_AGENDA_OUTLINED", toggle_view, "Mostra la vista completa" if compact else "Mostra solo le icone"),
    ]
    note = "i modelli senza un'area" if page == GENERAL else AREA_BY_KEY[page].covers
    controls: List[ft.Control] = [W.screen_header(info.label, info.nickname, "le ricette fatte di blocchi: ogni voce nasce da un modello", actions=actions), W.section_label(_page_label(page)), W.caption(note)]
    if not templates:
        controls.append(
            W.empty_state(
                "Non hai ancora modelli. Parti da una Scuola già pronta o crea il tuo, blocco per blocco.",
                "DASHBOARD_CUSTOMIZE_OUTLINED",
                W.primary_button("Vai alle Scuole", lambda _: ctx.go("/scuole"), icon="SCHOOL_OUTLINED"),
            )
        )
    elif not groups:
        controls.append(W.caption("Nessun modello in questa pagina, per ora."))
    for label, rows in groups:
        controls.append(W.section_label(label))
        if compact:
            controls.append(ft.Row([_icon_tile(ctx, row) for row in rows], wrap=True, spacing=6, run_spacing=6))
        else:
            controls.append(ft.ResponsiveRow([_template_tile(ctx, row, pinned, pin) for row in rows], spacing=10, run_spacing=10))
    pages = ft.GestureDetector(content=W.screen(controls, ctx.wide), on_long_press_move_update=moved, on_long_press_end=released, expand=True)
    # The bar of the areas sits at the bottom, under the thumb.
    bar = ft.Container(_page_bar(ctx, page, choose), padding=ft.Padding.symmetric(horizontal=8, vertical=6), border=ft.Border(top=ft.BorderSide(1, T.BORDER)))
    return ft.Container(ft.Column([pages, bar], spacing=0, expand=True), bgcolor=W.fade(_page_color(page), AREA_TINT), expand=True)


# * — export —


def export_dialog(ctx: AppContext) -> None:
    with ctx.store() as store:
        templates = store.list_templates()
    chosen: Dict[str, bool] = {template.slug: False for template in templates}
    name = W.text_input("I miei modelli", label="Nome del pacchetto")
    error = W.error_text()

    def toggle(slug: str, value: Optional[bool]) -> None:
        chosen[slug] = bool(value)

    boxes = [
        ft.Checkbox(label=f"{template.name}  ({template.slug})", value=False, on_change=lambda e, slug=template.slug: toggle(slug, e.control.value), active_color=T.ACCENT)
        for template in templates
    ]

    def do_export(_: Any) -> None:
        slugs = [slug for slug, wanted in chosen.items() if wanted]
        try:
            with ctx.store() as store:
                path = vm.export_templates(store, ctx.folder, slugs, name.value or "", ctx.now())
        except (ValueError, StoreError, OSError) as problem:
            error.value = str(problem)
            error.visible = True
            ctx.update(error)
            return
        ctx.close_dialog()
        show_export_result(ctx, path)

    dialog = ft.AlertDialog(
        title="Esporta i modelli",
        content=ft.Container(
            ft.Column(
                [
                    W.body("Solo la struttura dei modelli, mai le tue voci: puoi condividerlo senza timori.", dim=True),
                    W.wide(name),
                    ft.Column(boxes, spacing=0, scroll=ft.ScrollMode.AUTO, height=280),
                    error,
                ],
                spacing=10,
                tight=True,
            ),
            width=440,
        ),
        actions=[W.text_button("Annulla", ctx.close_dialog, color=T.TEXT), W.primary_button("Esporta", do_export, icon="DOWNLOAD")],
    )
    ctx.show_dialog(dialog)


def show_export_result(ctx: AppContext, path: Any) -> None:
    dialog = ft.AlertDialog(
        title="Pacchetto salvato",
        content=ft.Column(
            [
                W.body("L'ho salvato nella cartella dati, sotto exports:"),
                W.panel(W.body(str(path), selectable=True, size=13), padding=10, bgcolor=T.BG),
                W.caption("Scegliere un'altra cartella sarà possibile in una prossima versione."),
            ],
            spacing=10,
            tight=True,
        ),
        actions=[W.primary_button("Va bene", ctx.close_dialog)],
    )
    ctx.toast(f"Esportato in {path}")
    ctx.show_dialog(dialog)


# * — Scuole: built-in packs —


class PacksScreen:
    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx
        self.plan_holders: Dict[str, ft.Column] = {}

    def build(self) -> ft.Control:
        packs = builtin_packs()
        with self.ctx.store() as store:
            installed = [template.slug for template in store.list_templates()]
        controls: List[ft.Control] = [
            W.screen_header(
                "Pacchetti",
                NOMENCLATURE["pack"].name,
                "modelli pronti, raccolti come le scuole filosofiche antiche. Installarli non tocca le tue voci.",
                on_back=self.ctx.back,
            )
        ]
        for pack in packs:
            controls.append(self._pack_panel(vm.pack_card(pack, installed)))
        return W.screen(controls, self.ctx.wide)

    def _pack_panel(self, card: vm.PackCard) -> ft.Control:
        holder = ft.Column(spacing=8, visible=False)
        self.plan_holders[card.id] = holder
        names = ft.Row([W.pill(name) for name in card.template_names], wrap=True, spacing=6, run_spacing=6)
        return W.panel(
            ft.Column(
                [
                    ft.Row(
                        [ft.Column([W.h2(card.name), W.caption(card.installed_label)], spacing=2, expand=True)],
                    ),
                    W.body(card.description, dim=True),
                    names,
                    ft.Row([W.secondary_button("Vedi cosa cambia", lambda _, pack_id=card.id: self.preview(pack_id), icon="VISIBILITY_OUTLINED")], alignment=ft.MainAxisAlignment.END),
                    holder,
                ],
                spacing=10,
            )
        )

    def preview(self, pack_id: str) -> None:
        pack = next(pack for pack in builtin_packs() if pack.id == pack_id)
        with self.ctx.store() as store:
            plan = plan_install(pack, store)
        holder = self.plan_holders[pack_id]
        rows: List[ft.Control] = [W.divider(), W.body(f"Piano: {vm.plan_summary(plan)}.", size=14)]
        for row in vm.plan_rows(plan):
            detail = row.target_slug if not row.reason else f"{row.target_slug} · {row.reason}"
            rows.append(
                ft.Row(
                    [
                        ft.Container(W.pill(row.action_label, row.color), width=140),
                        ft.Column([W.body(row.template_name, size=14), W.caption(detail)], spacing=0, expand=True),
                    ],
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )
        has_changes = vm.plan_has_changes(plan)
        rows.append(
            ft.Row(
                [
                    W.text_button("Chiudi", lambda _: self.hide(pack_id), color=T.TEXT),
                    W.primary_button("Installa" if has_changes else "Già tutto installato", lambda _: self.install(pack_id), icon="DOWNLOAD_DONE", disabled=not has_changes),
                ],
                alignment=ft.MainAxisAlignment.END,
                spacing=8,
            )
        )
        holder.controls = rows
        holder.visible = True
        self.ctx.update(holder)

    def hide(self, pack_id: str) -> None:
        holder = self.plan_holders[pack_id]
        holder.visible = False
        self.ctx.update(holder)

    def install(self, pack_id: str) -> None:
        pack = next(pack for pack in builtin_packs() if pack.id == pack_id)
        try:
            with self.ctx.store() as store:
                installed = apply_install(plan_install(pack, store), store)
        except (StoreError, ValueError) as problem:
            self.ctx.toast(str(problem), error=True)
            return
        count = len(installed)
        self.ctx.data_changed()
        self.ctx.toast(f"{pack.name}: {'1 modello installato' if count == 1 else f'{count} modelli installati'}.")
        self.ctx.refresh()


def build_packs(ctx: AppContext, route: Route) -> ft.Control:
    return PacksScreen(ctx).build()
