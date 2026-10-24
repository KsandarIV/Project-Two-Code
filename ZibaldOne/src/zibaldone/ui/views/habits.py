"""Askesis (0.2.7): habits marked one day at a time. Streaks come from `core/habits`; the tone stays neutral (ADR-0008)."""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Callable, List, Optional

import flet as ft

from zibaldone.core import habits as H
from zibaldone.storage.database import StoreError
from zibaldone.ui import theme as T
from zibaldone.ui import widgets as W
from zibaldone.ui.context import AppContext
from zibaldone.ui.navigation import Route

DEFAULT_AREA = "salute"
WEEK_DAYS = 7


@dataclass(frozen=True)
class HabitRow:
    habit: H.Habit
    streak: H.Streak
    marks: List[bool]  # the last seven days, today last


def installed(store: Any) -> bool:
    return all(store.find_template(slug) is not None for slug in (H.HABIT, H.PRACTICE))


def load_rows(store: Any, today: date, area: str = "", include_inactive: bool = False) -> List[HabitRow]:
    rows: List[HabitRow] = []
    for habit in H.load_habits(store, include_inactive=include_inactive):
        if area and habit.area != area:
            continue
        practices = H.practices_of(store, habit.id)
        marks = [today - timedelta(days=WEEK_DAYS - 1 - back) in practices for back in range(WEEK_DAYS)]
        rows.append(HabitRow(habit, H.streak(habit, practices, today), marks))
    return rows


def streak_label(habit: H.Habit, streak: H.Streak) -> str:
    """«5 giorni di fila», «3 settimane di fila», or the plain count of the week when there is no run."""
    unit = ("giorno", "giorni") if habit.every == "day" else ("settimana", "settimane")
    if streak.current:
        return f"{streak.current} {unit[streak.current != 1]} di fila"
    if habit.every == "week":
        return f"{streak.done_this_week}/{streak.target_week} questa settimana"
    return "nessuna serie in corso"


def _quantity(text: str) -> Optional[str]:
    return text.strip() or None


def _toggle(ctx: AppContext, row: HabitRow, day: date, quantity: Callable[[], str]) -> Callable[[Any], None]:
    def toggle(_: Any) -> None:
        try:
            with ctx.store() as store:
                if row.marks[-1]:
                    H.unmark(store, row.habit.id, day)
                else:
                    H.mark(store, row.habit.id, day, _quantity(quantity()))
        except (H.HabitError, StoreError) as problem:
            ctx.toast(str(problem), error=True)
            return
        ctx.data_changed()
        ctx.refresh()

    return toggle


def _week_bar(row: HabitRow, today: date) -> ft.Control:
    days = [today - timedelta(days=WEEK_DAYS - 1 - back) for back in range(WEEK_DAYS)]
    cells = [
        ft.Container(
            width=14,
            height=14,
            border_radius=4,
            bgcolor=T.SUCCESS if done else T.BORDER,
            tooltip=f"{day.day:02d}/{day.month:02d}: " + ("segnato" if done else "non segnato"),
        )
        for day, done in zip(days, row.marks)
    ]
    return ft.Row(cells, spacing=4)


def _habit_row(ctx: AppContext, row: HabitRow, today: date, detail: bool = False) -> ft.Control:
    habit, streak = row.habit, row.streak
    done = row.marks[-1]
    field = W.text_input(f"{habit.goal:g}" if habit.goal is not None else "", width=84, dense=True, hint_text=habit.unit, tooltip=f"Quantità ({habit.unit})")
    field.visible = bool(habit.unit) and not done
    button = W.secondary_button("Togli", _toggle(ctx, row, today, lambda: field.value or ""), icon="UNDO") if done else W.primary_button("Segna", _toggle(ctx, row, today, lambda: field.value or ""), icon="CHECK")
    sub = streak_label(habit, streak)
    if detail:
        sub += f" · la più lunga: {streak.longest}"
    lines: List[ft.Control] = [W.body(habit.name, size=15, weight=ft.FontWeight.W_600), W.caption(sub)]
    if detail:
        lines.append(_week_bar(row, today))
    right: List[ft.Control] = [field, button] if habit.active else [W.pill("in pausa", T.TEXT_DIM)]
    return ft.Container(
        ft.Row(
            [ft.Column(lines, spacing=3, expand=True)] + right,
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            wrap=True,
        ),
        padding=ft.Padding.symmetric(vertical=6, horizontal=2),
    )


def _panel(ctx: AppContext, rows: List[HabitRow], today: date, detail: bool = False) -> ft.Control:
    return W.panel(ft.Column([_habit_row(ctx, row, today, detail) for row in rows], spacing=4))


def today_panel(ctx: AppContext, store: Any, today: date) -> Optional[ft.Control]:
    """The «Abitudini di oggi» block of Oggi; None when the pack is missing or no habit is active."""
    if not installed(store):
        return None
    rows = load_rows(store, today)
    if not rows:
        return None
    return ft.Column(
        [
            W.section_label("Abitudini di oggi", "Askesis"),
            _panel(ctx, rows, today),
            ft.Row([W.text_button("Tutte le abitudini", lambda _: ctx.go("/abitudini"), icon="CHECKLIST")], alignment=ft.MainAxisAlignment.END),
        ],
        spacing=8,
    )


def area_panel(ctx: AppContext, store: Any, area: str, today: date) -> Optional[ft.Control]:
    """The habits of one area, with their streaks; None when it has none."""
    if not installed(store):
        return None
    rows = load_rows(store, today, area=area)
    if not rows:
        return None
    return ft.Column([W.section_label("Abitudini", "Askesis"), _panel(ctx, rows, today)], spacing=8)


def _install(ctx: AppContext) -> Callable[[Any], None]:
    def install(_: Any) -> None:
        from zibaldone.core.packs import apply_install, find_builtin_pack, plan_install

        try:
            with ctx.store() as store:
                pack = find_builtin_pack(H.PACK_NAME)
                if pack is not None:
                    apply_install(plan_install(pack, store), store)
        except (StoreError, ValueError) as problem:
            ctx.toast(str(problem), error=True)
            return
        ctx.data_changed()
        ctx.toast("Askesis · Abitudini installato.")
        ctx.refresh()

    return install


def build(ctx: AppContext, route: Route) -> ft.Control:
    today = ctx.now().date()
    with ctx.store() as store:
        ready = installed(store)
        rows = load_rows(store, today, include_inactive=True) if ready else []
    header = W.screen_header("Abitudini", "Askesis", "i rituali di ogni giorno, con la serie che si conta da sola", on_back=ctx.back)
    if not ready:
        return W.screen(
            [
                header,
                W.panel(
                    ft.Column(
                        [
                            W.body("Rituali da segnare giorno per giorno, ogni giorno o qualche volta a settimana, con la serie di giorni di fila e l'ultima settimana. Arrivano con la Scuola «Askesis · Abitudini»."),
                            ft.Row([W.primary_button("Installa «Askesis · Abitudini»", _install(ctx), icon="DOWNLOAD")], alignment=ft.MainAxisAlignment.END),
                        ],
                        spacing=10,
                    ),
                    border_color=W.fade(T.ACCENT, 0.45),
                ),
            ],
            ctx.wide,
        )
    controls: List[ft.Control] = [header, ft.Row([W.primary_button("Nuovo rituale", lambda _: ctx.go(f"/scrivi/{H.HABIT}/{DEFAULT_AREA}"), icon="ADD")], alignment=ft.MainAxisAlignment.END)]
    if rows:
        controls.append(_panel(ctx, rows, today, detail=True))
    else:
        controls.append(W.empty_state("Nessun rituale, per ora. Scegline uno piccolo, anche solo un bicchiere d'acqua.", "CHECKLIST"))
    return W.screen(controls, ctx.wide)
