"""Oggi · Hic et nunc: the day at a glance."""

from typing import Any, List

import flet as ft

from zibaldone.ui import services
from zibaldone.ui import theme as T
from zibaldone.ui import viewmodels as vm
from zibaldone.ui import widgets as W
from zibaldone.ui.context import AppContext
from zibaldone.ui.navigation import Route, section
from zibaldone.ui.views.common import choose_template


def build(ctx: AppContext, route: Route) -> ft.Control:
    now = ctx.now()
    reminder = services.in_app_reminder(ctx.folder, now)
    config, _ = services.reminder_config(ctx.folder)
    with ctx.store() as store:
        streak = services.streak_days(store, now.date())
        model = vm.build_today(store, now, reminder, streak, config)

    info = section("oggi")
    actions: List[ft.Control] = [W.primary_button("Nuova voce", lambda _: choose_template(ctx), icon="ADD")]
    if model.streak_label:
        actions.append(W.pill(model.streak_label, T.ACCENT_2, icon="LOCAL_FIRE_DEPARTMENT"))
    controls: List[ft.Control] = [
        W.screen_header(info.label, info.nickname, f"{model.greeting}, è {model.date_label}.", actions=actions),
    ]
    if model.reminder is not None:
        controls.append(_reminder_banner(ctx, model.reminder))
    controls.append(_quote(model.quote))
    controls.append(W.section_label("I tre momenti", "Stoa"))
    if model.diario_installed:
        controls.append(ft.ResponsiveRow([_moment_card(ctx, card) for card in model.moments], spacing=12, run_spacing=12))
    else:
        controls.append(
            W.empty_state(
                "Il diario non è ancora installato. Con la Scuola «Stoa · Diario» trovi mattina, metà giornata e sera, "
                "più il check-in delle otto aree.",
                "WB_SUNNY",
                W.primary_button("Vai alle Scuole", lambda _: ctx.go("/scuole"), icon="SCHOOL_OUTLINED"),
            )
        )
    if model.areas.installed:
        controls.append(W.section_label("Le otto aree", "Eudaimonia"))
        controls.append(_areas(ctx, model.areas))
    controls.append(W.section_label("Le voci di oggi"))
    if model.entries:
        for row in model.entries:
            controls.append(
                W.entry_tile(row.title, row.template_name, row.summary, row.icon, row.color, lambda _, entry_id=row.id: ctx.go(f"/voci/{entry_id}"))
            )
    else:
        controls.append(W.empty_state("Nessuna voce oggi, per ora. Quando vuoi, il tuo zibaldone è qui.", "EDIT_NOTE"))
    return W.screen(controls, ctx.wide)


def _reminder_banner(ctx: AppContext, banner: vm.ReminderBanner) -> ft.Control:
    return W.panel(
        ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.NOTIFICATIONS_ACTIVE_OUTLINED, color=T.ACCENT_2, size=22),
                        ft.Column([W.body(banner.title, size=13, dim=True), W.body(banner.body, size=15)], spacing=2, expand=True),
                    ],
                    spacing=12,
                ),
                ft.Row([W.primary_button("Scrivi ora", lambda _: ctx.go(f"/scrivi/{banner.moment}"), icon="EDIT")], alignment=ft.MainAxisAlignment.END),
            ],
            spacing=8,
        ),
        border_color=W.fade(T.ACCENT_2, 0.55),
    )


def _quote(quote: Any) -> ft.Control:
    return W.panel(
        ft.Row(
            [
                ft.Icon(ft.Icons.FORMAT_QUOTE, color=T.ACCENT, size=26),
                ft.Column(
                    [
                        W.caption("Pensiero del giorno"),
                        ft.Text(f"«{quote.text}»", size=18, italic=True, color=T.TEXT),
                        W.caption(f"— {quote.author}, {quote.source}"),
                    ],
                    spacing=4,
                    expand=True,
                ),
            ],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )
    )


def _moment_card(ctx: AppContext, card: vm.MomentCard) -> ft.Control:
    if card.written:
        status: ft.Control = W.pill("scritto", T.SUCCESS, icon="CHECK")
        button: ft.Control = W.secondary_button("Apri", lambda _: ctx.go(f"/voci/{card.entry_id}"), icon="ARTICLE_OUTLINED")
    else:
        status = W.caption(f"dalle {card.time}" if card.time else "ancora da scrivere")
        button = W.primary_button("Scrivi", lambda _: ctx.go(f"/scrivi/{card.key}"), icon="EDIT")
    return W.panel(
        ft.Column(
            [
                ft.Row(
                    [
                        W.template_badge(card.icon, card.color),
                        ft.Column([W.body(card.label, size=16, weight=ft.FontWeight.W_600), W.caption(card.template_name)], spacing=0, expand=True),
                    ],
                    spacing=12,
                ),
                ft.Row([status, button], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ],
            spacing=14,
        ),
        col={"xs": 12, "md": 4},
    )


def _areas(ctx: AppContext, areas: vm.AreaCheckin) -> ft.Control:
    if not areas.done:
        avatars = ft.Row([W.mascot_avatar(score.mascot, 30) for score in areas.scores], spacing=6, wrap=True, run_spacing=6)
        return W.panel(
            ft.Column(
                [
                    avatars,
                    W.body("Come vanno oggi le otto aree della tua vita? Un tocco per ciascuna, senza pensarci troppo."),
                    ft.Row([W.primary_button("Fai il check-in", lambda _: ctx.go("/scrivi/aree"), icon="DONUT_LARGE")], alignment=ft.MainAxisAlignment.END),
                ],
                spacing=12,
            )
        )
    tiles = []
    for score in areas.scores:
        value = f"{score.value}/{score.maximum}" if score.value is not None else "—"
        tiles.append(
            ft.Container(
                ft.Row(
                    [
                        W.mascot_avatar(score.mascot, 30),
                        ft.Column(
                            [
                                ft.Row([W.body(score.label, size=13), W.caption(value)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                W.meter(score.fraction, score.color),
                            ],
                            spacing=6,
                            expand=True,
                        ),
                    ],
                    spacing=10,
                ),
                col={"xs": 12, "sm": 6, "xl": 3},
                padding=ft.Padding.symmetric(vertical=4),
            )
        )
    return W.panel(
        ft.Column(
            [
                ft.ResponsiveRow(tiles, spacing=16, run_spacing=10),
                ft.Row([W.text_button("Modifica il check-in", lambda _: ctx.go(f"/voci/{areas.entry_id}/modifica"), icon="EDIT")], alignment=ft.MainAxisAlignment.END),
            ],
            spacing=8,
        )
    )
