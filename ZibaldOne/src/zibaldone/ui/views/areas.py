"""Eudaimonia (0.2.0): the 8 life areas, all together and one by one."""

from typing import Any, Callable, List

import flet as ft

from zibaldone.core.areas import AreaError, add_todo, set_todo
from zibaldone.core.brand import NOMENCLATURE
from zibaldone.storage.database import StoreError
from zibaldone.ui import forms
from zibaldone.ui import theme as T
from zibaldone.ui import viewmodels as vm
from zibaldone.ui import widgets as W
from zibaldone.ui.context import AppContext
from zibaldone.ui.navigation import Route
from zibaldone.ui.views.common import not_found

CHART_HEIGHT = 84
PACK_NOTE = "Check-in di una sola area, obiettivi e cose da fare arrivano con la Scuola «Liceo · Aree»."


def _install_pack(ctx: AppContext) -> Callable[[Any], None]:
    def install(_: Any) -> None:
        try:
            with ctx.store() as store:
                count = vm.install_areas_pack(store)
        except (StoreError, ValueError) as problem:
            ctx.toast(str(problem), error=True)
            return
        ctx.data_changed()
        ctx.toast(f"Liceo · Aree installato: {count} modelli." if count else "Liceo · Aree era già installato.")
        ctx.refresh()

    return install


def _pack_panel(ctx: AppContext) -> ft.Control:
    return W.panel(
        ft.Column(
            [
                W.body(PACK_NOTE),
                ft.Row([W.primary_button("Installa «Liceo · Aree»", _install_pack(ctx), icon="DOWNLOAD")], alignment=ft.MainAxisAlignment.END),
            ],
            spacing=10,
        ),
        border_color=W.fade(T.ACCENT, 0.45),
    )


# * — all the areas —


def build_overview(ctx: AppContext, route: Route) -> ft.Control:
    today = ctx.now().date()
    with ctx.store() as store:
        cards = vm.area_cards(store, today)
        missing = vm.areas_pack_missing(store)
    name = NOMENCLATURE["areas"]
    controls: List[ft.Control] = [
        W.screen_header("Le otto aree", name.name, "come va ogni parte della tua vita, con le sue cose da fare e i suoi obiettivi", on_back=ctx.back),
        W.caption(name.source),
    ]
    if missing:
        controls.append(_pack_panel(ctx))
    controls.append(ft.ResponsiveRow([_area_card(ctx, card) for card in cards], spacing=12, run_spacing=12))
    coming = vm.upcoming_rows()
    if coming:
        controls.append(W.section_label("In arrivo per tutte le aree"))
        controls.append(ft.ResponsiveRow([W.upcoming_card(item.title, item.teaser, item.when, col={"xs": 12, "md": 6}) for item in coming], spacing=12, run_spacing=12))
    return W.screen(controls, ctx.wide)


def _area_card(ctx: AppContext, card: vm.AreaCard) -> ft.Control:
    head: List[ft.Control] = [
        W.mascot_avatar(card.mascot, 38),
        ft.Column(
            [W.body(card.label, size=16, weight=ft.FontWeight.W_600), W.caption(card.mascot.name if card.mascot else "")],
            spacing=0,
            expand=True,
        ),
        ft.Text(card.score_label, size=16, weight=ft.FontWeight.W_600, color=T.TEXT),
    ]
    if card.trend_icon:
        head.append(ft.Icon(W.icon_of(card.trend_icon), color=card.color, size=18, tooltip=card.trend_label))
    rows: List[ft.Control] = [
        ft.Row(head, spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        W.meter(card.fraction, card.color),
        W.caption(card.counts_label),
    ]
    if card.upcoming:
        rows.append(ft.Row([W.pill("1 novità in arrivo" if card.upcoming == 1 else f"{card.upcoming} novità in arrivo", T.ACCENT_2, icon="AUTO_AWESOME")], wrap=True))
    return W.panel(ft.Column(rows, spacing=10), on_click=lambda _: ctx.go(f"/aree/{card.key}"), col={"xs": 12, "sm": 6, "lg": 3})


# * — one area —


class AreaScreen:
    def __init__(self, ctx: AppContext, key: str) -> None:
        self.ctx = ctx
        self.key = key
        self.todo_input = W.text_input("", hint_text="Che cosa c'è da fare?", on_submit=self.add, expand=True, dense=True)

    def build(self) -> ft.Control:
        ctx = self.ctx
        with ctx.store() as store:
            page = vm.area_page(store, self.key, ctx.now().date())
        self.page = page
        actions: List[ft.Control] = []
        if not page.missing:
            actions.append(W.primary_button("Check-in", lambda _: ctx.go(f"/scrivi/checkin_area/{page.key}"), icon="CENTER_FOCUS_STRONG"))
            actions.append(W.secondary_button("Obiettivo", lambda _: ctx.go(f"/scrivi/obiettivo/{page.key}"), icon="FLAG_OUTLINED"))
        if page.note_template:
            actions.append(W.secondary_button("Nota", lambda _: ctx.go(f"/scrivi/{page.note_template}/{page.key}"), icon="NOTE_ADD_OUTLINED"))
        mascot = page.mascot
        controls: List[ft.Control] = [
            W.screen_header(page.label, mascot.name if mascot else "", page.covers, on_back=ctx.back, actions=actions),
        ]
        if mascot is not None:
            controls.append(
                W.panel(
                    ft.Row(
                        [
                            W.mascot_avatar(mascot, 48),
                            ft.Column([W.body(f"{mascot.name}, {mascot.animal} · {mascot.philosopher}", size=13, dim=True), W.body(mascot.story, italic=True)], spacing=4, expand=True),
                        ],
                        spacing=14,
                        vertical_alignment=ft.CrossAxisAlignment.START,
                    ),
                    border_color=W.fade(page.color, 0.45),
                )
            )
        if page.missing:
            controls.append(_pack_panel(ctx))
        controls.append(self._score(page))
        controls.append(self._todos(page))
        controls.append(self._goals(page))
        if page.people:
            controls.append(self._people(page))
        controls.append(self._entries(page))
        if page.upcoming:
            controls.append(W.section_label(f"In arrivo per {page.label.lower()}"))
            controls.append(
                ft.ResponsiveRow([W.upcoming_card(item.title, item.teaser, item.when, page.color, col={"xs": 12, "md": 6}) for item in page.upcoming], spacing=12, run_spacing=12)
            )
        return W.screen(controls, ctx.wide)

    # — panels —

    def _score(self, page: vm.AreaPage) -> ft.Control:
        head: List[ft.Control] = [W.body("Punteggio", size=16, weight=ft.FontWeight.W_600), ft.Container(expand=True)]
        if page.trend:
            head.append(W.pill(page.trend_label, page.color, icon=page.trend_icon))
        head.append(ft.Text(page.score_label, size=20, weight=ft.FontWeight.W_700, color=T.TEXT))
        rows: List[ft.Control] = [ft.Row(head, spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER), W.caption(page.score_note)]
        if page.has_scores:
            rows.append(self._chart(page))
            rows.append(W.caption("Media di ogni settimana, dalle scale del check-in delle otto aree e dei check-in di quest'area."))
        return W.panel(ft.Column(rows, spacing=10))

    def _chart(self, page: vm.AreaPage) -> ft.Control:
        columns: List[ft.Control] = []
        for week in page.weeks:
            fraction = week.fraction
            height = 3 if fraction is None else max(4, round(fraction * CHART_HEIGHT))
            color = page.color if fraction is not None else T.BORDER
            tooltip = f"settimana del {week.label}: " + ("nessun punteggio" if week.average is None else f"{forms.format_number(round(week.average, 1))}/10")
            columns.append(
                ft.Container(
                    ft.Container(height=height, bgcolor=color, border_radius=4, tooltip=tooltip),
                    height=CHART_HEIGHT,
                    alignment=ft.Alignment.BOTTOM_CENTER,
                    expand=True,
                )
            )
        ends = ft.Row(
            [W.caption(f"settimana del {page.weeks[0].label}"), W.caption(f"settimana del {page.weeks[-1].label}")],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )
        return ft.Column([ft.Row(columns, spacing=4, vertical_alignment=ft.CrossAxisAlignment.END), ends], spacing=4)

    def _todos(self, page: vm.AreaPage) -> ft.Control:
        rows: List[ft.Control] = [W.body("Da fare" + (f" ({len(page.todos)})" if page.todos else ""), size=16, weight=ft.FontWeight.W_600)]
        for row in page.todos:
            rows.append(
                ft.Row(
                    [
                        ft.Checkbox(value=False, active_color=page.color, on_change=lambda e, row=row: self.tick(row, e.control.value)),
                        ft.Column([W.body(row.text, size=14), W.caption(row.where)], spacing=0, expand=True),
                    ],
                    spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )
        if not page.todos:
            rows.append(W.body("Niente da fare, per ora.", dim=True))
        if not page.missing:
            rows.append(ft.Row([self.todo_input, W.secondary_button("Aggiungi", self.add, icon="ADD_TASK")], spacing=8))
        else:
            rows.append(W.caption("Per aggiungere cose da fare installa «Liceo · Aree»."))
        return W.panel(ft.Column(rows, spacing=8))

    def _goals(self, page: vm.AreaPage) -> ft.Control:
        rows: List[ft.Control] = [W.body("Obiettivi", size=16, weight=ft.FontWeight.W_600)]
        for goal in page.goals:
            rows.append(
                W.panel(
                    ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Icon(ft.Icons.FLAG_OUTLINED if goal.active else ft.Icons.TASK_ALT, color=page.color if goal.active else T.SUCCESS, size=20),
                                    ft.Column([W.body(goal.title, size=15, weight=ft.FontWeight.W_600), W.caption(goal.meta)], spacing=0, expand=True),
                                    ft.Icon(ft.Icons.CHEVRON_RIGHT, color=T.TEXT_DIM, size=20),
                                ],
                                spacing=10,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            W.meter(goal.fraction, page.color),
                        ],
                        spacing=8,
                    ),
                    padding=ft.Padding.symmetric(horizontal=14, vertical=12),
                    on_click=lambda _, entry_id=goal.entry_id: self.ctx.go(f"/voci/{entry_id}"),
                )
            )
        if not page.goals:
            rows.append(W.body("Nessun obiettivo in quest'area. Un obiettivo ha i suoi passi, che compaiono anche tra le cose da fare.", dim=True))
        return W.panel(ft.Column(rows, spacing=8))

    def _people(self, page: vm.AreaPage) -> ft.Control:
        rows: List[ft.Control] = [W.body(f"Persone ({len(page.people)})", size=16, weight=ft.FontWeight.W_600)]
        buttons: List[ft.Control] = []
        if page.key == "famiglia":
            buttons.append(W.secondary_button("Albero", lambda _: self.ctx.go("/albero"), icon="ACCOUNT_TREE"))
        if len(page.people) > 1:
            buttons.append(W.secondary_button("Rete", lambda _: self.ctx.go(f"/rete/{page.key}"), icon="HUB"))
        if buttons:
            rows.append(ft.Row(buttons, wrap=True, spacing=8))
        for person in page.people:
            line = " · ".join(part for part in (person.roles, person.contact) if part)
            right: List[ft.Control] = [W.pill("da sentire", T.ACCENT_2, icon="WAVING_HAND")] if person.due else []
            rows.append(
                ft.Container(
                    ft.Row([ft.Column([W.body(person.name, size=15, weight=ft.FontWeight.W_600), W.caption(line)], spacing=0, expand=True), *right], spacing=8),
                    on_click=lambda _, person_id=person.id: self.ctx.go(f"/persone/{person_id}"),
                )
            )
        return W.panel(ft.Column(rows, spacing=10))

    def _entries(self, page: vm.AreaPage) -> ft.Control:
        rows: List[ft.Control] = [W.body(f"Le voci dell'area ({page.total})", size=16, weight=ft.FontWeight.W_600)]
        for row in page.entries:
            rows.append(W.entry_tile(row.title, f"{row.template_name} · {row.day_label}", row.summary, row.icon, row.color, lambda _, entry_id=row.id: self.ctx.go(f"/voci/{entry_id}")))
        if page.total > len(page.entries):
            rows.append(ft.Row([W.text_button("Vedile tutte nelle Voci", self.show_all, icon="LIST_ALT")]))
        if not page.entries:
            rows.append(W.body("Ancora nessuna voce.", dim=True))
        if page.template_names:
            rows.append(W.caption(f"Entrano da sole le voci di: {', '.join(page.template_names)}. Le altre, scegliendo l'area quando scrivi."))
        else:
            rows.append(W.caption("Ogni voce può entrare in quest'area: scegli l'area quando scrivi, oppure dai un'area a un modello nelle Forme."))
        return W.panel(ft.Column(rows, spacing=10))

    # — actions —

    def tick(self, row: vm.AreaTodoRow, done: Any) -> None:
        try:
            with self.ctx.store() as store:
                set_todo(store, row.todo, bool(done))
        except (AreaError, StoreError, ValueError) as problem:
            self.ctx.toast(str(problem), error=True)
            self.ctx.refresh()
            return
        self.ctx.data_changed()
        self.ctx.toast(f"Fatto: {row.text}.", action="Annulla", on_action=lambda: self.undo(row))
        self.ctx.refresh()

    def undo(self, row: vm.AreaTodoRow) -> None:
        try:
            with self.ctx.store() as store:
                set_todo(store, row.todo, False)
        except (AreaError, StoreError, ValueError):
            return
        self.ctx.data_changed()
        self.ctx.refresh()

    def add(self, _: Any = None) -> None:
        text = (self.todo_input.value or "").strip()
        if not text:
            return
        try:
            with self.ctx.store() as store:
                add_todo(store, self.key, text, day=self.ctx.now().date().isoformat())
        except (AreaError, StoreError, ValueError) as problem:
            self.ctx.toast(str(problem), error=True)
            return
        self.ctx.data_changed()
        self.ctx.toast("Aggiunto alle cose da fare.")
        self.ctx.refresh()

    def show_all(self, _: Any) -> None:
        self.ctx.memory["entries_query"] = vm.EntryQuery(area=self.key)
        self.ctx.go("/voci")


def build_area(ctx: AppContext, route: Route) -> ft.Control:
    try:
        return AreaScreen(ctx, route.arg).build()
    except ValueError:
        return not_found(ctx, "Quest'area non esiste. Le aree sono otto: personale, salute, finanze, famiglia, sociale, lavoro, studio e svago.")
