"""`zbone abitudini …`: Askesis (0.2.7), habits marked one day at a time, with their streaks."""

from datetime import date
from typing import Any, Dict, List, Optional, Tuple

import typer

from zibaldone.cli.common import fail, open_store
from zibaldone.core import habits as H
from zibaldone.storage.database import StoreError

habit_app = typer.Typer(help="Askesis: abitudini segnate giorno per giorno, con la serie di giorni.", no_args_is_help=False)


def _day(text: Optional[str]) -> date:
    try:
        return date.fromisoformat(text) if text else date.today()
    except ValueError:
        fail("il giorno si scrive AAAA-MM-GG, per esempio 2026-10-24")


def _unit(habit: H.Habit) -> str:
    return f" {habit.unit}" if habit.unit else ""


def _goal(habit: H.Habit) -> str:
    return f" (traguardo {habit.goal:f}{_unit(habit)})" if habit.goal is not None else ""


def _run(habit: H.Habit, result: H.Streak) -> str:
    this_week = f"{result.done_this_week} su {result.target_week} questa settimana"
    if habit.every == "week":
        return f"{H.run_text('week', result.current)}, {this_week}"
    return f"{H.run_text('day', result.current)}, {H.plural(result.done_this_week, 'giorno', 'giorni')} su 7 questa settimana"


def _load() -> Tuple[List[H.Habit], Dict[str, Dict[date, Any]]]:
    try:
        with open_store() as store:
            if store.find_template(H.HABIT) is None:
                fail(f"manca la Scuola «Askesis · Abitudini»: zbone pack install {H.PACK_NAME}")
            habits = H.load_habits(store)
            return habits, {habit.id: H.practices_of(store, habit.id) for habit in habits}
    except StoreError as error:
        fail(str(error))


@habit_app.callback(invoke_without_command=True)
def today(ctx: typer.Context) -> None:
    """Oggi: che cosa resta da fare e la serie di ciascun rituale."""
    if ctx.invoked_subcommand is not None:
        return
    habits, practices = _load()
    if not habits:
        typer.echo("Nessun rituale attivo. Creane uno con: zbone entry add rituale")
        return
    now = date.today()
    due = {habit.id for habit in H.due_today(habits, practices, now)}
    for habit in habits:
        result = H.streak(habit, practices[habit.id], now)
        typer.echo(f"{'·' if habit.id in due else '✓'} {habit.name}{_goal(habit)}: {_run(habit, result)}")
    typer.echo(f"\nDa fare oggi: {len(due)} su {len(habits)}.")


def _habit_of(habits: List[H.Habit], name: str) -> H.Habit:
    try:
        return H.find_habit(habits, name)
    except H.HabitError as error:
        fail(str(error))


@habit_app.command("segna")
def done(name: str = typer.Argument(..., metavar="NOME", help="anche solo le prime lettere"), quantity: Optional[str] = typer.Argument(None, metavar="QUANTITÀ"), day: Optional[str] = typer.Option(None, "--giorno", help="AAAA-MM-GG; di base oggi")) -> None:
    """Segna un rituale come fatto (con la quantità, se ne ha una)."""
    habits, _ = _load()
    habit = _habit_of(habits, name)
    try:
        with open_store() as store:
            entry = H.mark(store, habit.id, _day(day), quantity)
    except (H.HabitError, StoreError, ValueError) as error:
        fail(str(error))
    typer.echo(f"Segnato «{habit.name}» ({entry.day}).")


@habit_app.command("togli")
def undo(name: str = typer.Argument(..., metavar="NOME"), day: Optional[str] = typer.Option(None, "--giorno", help="AAAA-MM-GG; di base oggi")) -> None:
    """Toglie la pratica di un giorno."""
    habits, _ = _load()
    habit = _habit_of(habits, name)
    try:
        with open_store() as store:
            removed = H.unmark(store, habit.id, _day(day))
    except (H.HabitError, StoreError) as error:
        fail(str(error))
    typer.echo(f"Tolto «{habit.name}»." if removed else f"«{habit.name}» non era segnato in quel giorno.")


@habit_app.command("serie")
def series() -> None:
    """La serie attuale e la più lunga di ogni rituale."""
    habits, practices = _load()
    if not habits:
        typer.echo("Nessun rituale attivo.")
        return
    now = date.today()
    for habit in habits:
        result = H.streak(habit, practices[habit.id], now)
        unit = ("settimana", "settimane") if habit.every == "week" else ("giorno", "giorni")
        typer.echo(f"{habit.name}: attuale {H.plural(result.current, *unit)}, la più lunga {H.plural(result.longest, *unit)}")
