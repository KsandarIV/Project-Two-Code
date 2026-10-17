"""Modelli · Forme: the templates by category, the built-in packs (Scuole) and the export."""

from typing import Any, Dict, List, Optional

import flet as ft

from zibaldone.core.brand import NOMENCLATURE
from zibaldone.core.packs import apply_install, builtin_packs, plan_install
from zibaldone.storage.database import StoreError
from zibaldone.ui import theme as T
from zibaldone.ui import viewmodels as vm
from zibaldone.ui import widgets as W
from zibaldone.ui.context import AppContext
from zibaldone.ui.navigation import Route, section


def build_list(ctx: AppContext, route: Route) -> ft.Control:
    info = section("modelli")
    with ctx.store() as store:
        templates = store.list_templates()
        counts = {template.slug: store.count_entries(template.slug) for template in templates}
    groups = vm.group_templates(templates, counts)
    actions = [
        W.primary_button("Nuovo modello", lambda _: ctx.go("/modelli/nuovo"), icon="ADD"),
        W.secondary_button(f"{NOMENCLATURE['pack'].name} · pacchetti", lambda _: ctx.go("/scuole"), icon="SCHOOL_OUTLINED"),
        W.secondary_button("Esporta", lambda _: export_dialog(ctx), icon="DOWNLOAD", disabled=not templates),
    ]
    controls: List[ft.Control] = [W.screen_header(info.label, info.nickname, "le ricette fatte di blocchi: ogni voce nasce da un modello", actions=actions)]
    if not groups:
        controls.append(
            W.empty_state(
                "Non hai ancora modelli. Parti da una Scuola già pronta o crea il tuo, blocco per blocco.",
                "DASHBOARD_CUSTOMIZE_OUTLINED",
                W.primary_button("Vai alle Scuole", lambda _: ctx.go("/scuole"), icon="SCHOOL_OUTLINED"),
            )
        )
    for label, rows in groups:
        controls.append(W.section_label(label))
        tiles = []
        for row in rows:
            tiles.append(
                W.panel(
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
                            W.icon_button("EDIT_NOTE", lambda _, slug=row.slug: ctx.go(f"/scrivi/{slug}"), "Scrivi una voce", color=T.ACCENT),
                        ],
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.Padding.symmetric(horizontal=14, vertical=12),
                    on_click=lambda _, slug=row.slug: ctx.go(f"/modelli/{slug}"),
                    col={"xs": 12, "lg": 6},
                )
            )
        controls.append(ft.ResponsiveRow(tiles, spacing=10, run_spacing=10))
    return W.screen(controls, ctx.wide)


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
                        [ft.Column([W.h2(card.name), W.caption(f"versione {card.version} · {card.installed_label}")], spacing=2, expand=True)],
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
