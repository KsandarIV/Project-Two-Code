"""Theoria (0.1.4): the statistics of a week or a month, and the review ready to complete."""

from typing import Any, Callable, List

import flet as ft

from zibaldone.core.brand import NOMENCLATURE
from zibaldone.core.stats import number, short_day, trend_words
from zibaldone.ui import theme as T
from zibaldone.ui import viewmodels as vm
from zibaldone.ui import widgets as W
from zibaldone.ui.context import AppContext
from zibaldone.ui.navigation import Route


def build(ctx: AppContext, route: Route) -> ft.Control:
    query: vm.StatsQuery = ctx.memory.setdefault("stats_query", vm.StatsQuery())
    today = ctx.now().date()
    with ctx.store() as store:
        result = vm.load_stats(store, query, today)

    def show(kind: str) -> Callable[[Any], None]:
        def pick(_: Any) -> None:
            if query.kind != kind:
                query.kind, query.day = kind, ""
                ctx.refresh()

        return pick

    def move(step: int) -> None:
        if vm.move_period(query, today, step):
            ctx.refresh()

    def make_review(_: Any) -> None:
        with ctx.store() as store:
            entry, created = vm.prepare_review(store, query.kind, vm.stats_day(query, today), today)
        if entry is None:
            ctx.toast("Per la revisione serve il diario: installalo da Modelli → Scuole (Stoa · Diario).")
            return
        ctx.data_changed()
        if created:
            ctx.toast("Revisione preparata con i dati del periodo: rileggila e completala.")
            ctx.go(f"/voci/{entry.id}/modifica")
        else:
            ctx.toast("C'è già una revisione per questo periodo: eccola.")
            ctx.go(f"/voci/{entry.id}")

    name = NOMENCLATURE["stats"]
    period = result.period
    at_current = period.contains(today)
    is_week = query.kind != "month"
    switch = ft.Row(
        [
            (W.primary_button if is_week else W.secondary_button)("Settimana", show("week")),
            (W.secondary_button if is_week else W.primary_button)("Mese", show("month")),
            W.icon_button("CHEVRON_LEFT", lambda _: move(-1), f"{period.noun.capitalize()} prima", color=T.TEXT),
            W.icon_button("CHEVRON_RIGHT", lambda _: move(1), f"{period.noun.capitalize()} dopo", color=T.TEXT, disabled=at_current),
        ],
        wrap=True,
        spacing=8,
        run_spacing=8,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )
    review_label = "Revisione della settimana" if is_week else "Revisione del mese"
    controls: List[ft.Control] = [
        W.screen_header("Statistiche", name.name, period.label, on_back=ctx.back, actions=[W.primary_button(review_label, make_review, icon="AUTO_STORIES")]),
        switch,
        _writing(result),
    ]
    if result.activity.total:
        controls += [panel for panel in (_mood(result), _areas(result), _other_scores(result), _collections(ctx, result), _people(ctx, result), _open_items(ctx, result)) if panel is not None]
    controls.append(W.caption("I numeri si calcolano qui, dalle tue voci: non escono dal dispositivo."))
    return W.screen(controls, ctx.wide)


def _titled(title: str, rows: List[ft.Control]) -> ft.Control:
    return W.panel(ft.Column([W.body(title, size=16, weight=ft.FontWeight.W_600)] + rows, spacing=10))


def _writing(result: Any) -> ft.Control:
    activity = result.activity
    rows: List[ft.Control] = [W.body(vm.writing_line(result), dim=not activity.total)]
    if activity.per_template:
        rows.append(ft.Row([W.pill(f"{template_name} {count}") for _, template_name, count in activity.per_template[:8]], wrap=True, spacing=6, run_spacing=6))
    if activity.current_streak > 1:
        rows.append(W.caption(f"Giorni di fila con almeno una voce: {activity.current_streak} (la serie più lunga: {activity.longest_streak})."))
    elif activity.longest_streak > 1:
        rows.append(W.caption(f"La serie più lunga di giorni con almeno una voce: {activity.longest_streak}."))
    return _titled("Scrittura", rows)


def _mood(result: Any) -> Any:
    mood = result.mood
    if mood.average is None:
        return None
    trend = trend_words(mood, result.period.noun)
    rows: List[ft.Control] = [W.body(f"Media {number(mood.average)}" + (f", {trend}" if trend else "") + ".")]
    for point in result.mood_points:
        fraction = None if point.average is None else (point.average - 1) / 4
        rows.append(W.labelled_meter(vm.mood_point_label(point), fraction, number(point.average) if point.average is not None else "—", T.ACCENT_2))
    return _titled("Umore (da 1 a 5)", rows)


def _areas(result: Any) -> Any:
    areas = [stat for stat in result.scales if stat.area]
    if not areas:
        return None
    rows: List[ft.Control] = [W.labelled_meter(stat.label, stat.normalized, f"{number(stat.average)}/{stat.high}") for stat in areas]
    if result.best_area and result.worst_area:
        rows.append(W.caption(f"Più in alto: {result.best_area.label}. Quella che chiede più cura: {result.worst_area.label}."))
    return _titled("Aree della vita", rows)


def _other_scores(result: Any) -> Any:
    others = [stat for stat in result.scales if not stat.area]
    if not others:
        return None
    return _titled("Altri punteggi", [W.labelled_meter(f"{stat.label} · {stat.template_name}", stat.normalized, f"{number(stat.average)} su {stat.high}") for stat in others])


def _open(ctx: AppContext, entry_id: str) -> Callable[[Any], None]:
    return lambda _: ctx.go(f"/voci/{entry_id}")


def _collections(ctx: AppContext, result: Any) -> Any:
    rows: List[ft.Control] = []
    for item in result.in_progress[:8]:
        details = [item.template_name, item.status_label + (f" {item.percent}%" if item.percent is not None else "")]
        if item.bookmark:
            details.append(item.bookmark)
        rows.append(W.entry_tile(item.title, " · ".join(details), "", "BOOKMARK_OUTLINE", T.ACCENT, _open(ctx, item.entry_id)))
    for item in result.completed:
        rows.append(W.entry_tile(item.title, f"{item.template_name} · completato", "", "TASK_ALT", T.SUCCESS, _open(ctx, item.entry_id)))
    return _titled("Collezioni", rows) if rows else None


def _people(ctx: AppContext, result: Any) -> Any:
    if not result.people:
        return None
    rows = [W.entry_tile(person.title, "1 voce" if person.count == 1 else f"{person.count} voci", "", "PERSON_OUTLINE", T.ACCENT, _open(ctx, person.entry_id)) for person in result.people]
    return _titled("Persone più presenti", rows)


def _open_items(ctx: AppContext, result: Any) -> Any:
    if not result.open_items:
        return None
    rows = [W.entry_tile(item.text, f"{item.template_name} · {short_day(item.day)}", "", "CHECK_BOX_OUTLINE_BLANK", T.TEXT_DIM, _open(ctx, item.entry_id)) for item in result.open_items[:10]]
    return _titled(f"Ancora aperti ({len(result.open_items)})", rows)
