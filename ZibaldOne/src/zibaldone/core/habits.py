"""Askesis (0.2.7): habits, marked one day at a time, with streaks worked out in memory.

A `rituale` is the habit (every day, or a few times a week, with an optional
quantity such as «8 bicchieri»); a `pratica` is one day it was done, linked to
its rituale. Nothing is sealed: habits are not sensitive. The streaks reuse
`core/stats.streaks`. The tone stays neutral (ADR-0008): numbers, never blame.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set

from zibaldone.core.errors import StoreError
from zibaldone.core.stats import streaks

HABIT, PRACTICE = "rituale", "pratica"
PACK_NAME = "askesis"
DAILY, WEEKLY = "Ogni giorno", "Più volte a settimana"
DEFAULT_TIMES = 3


class HabitError(ValueError):
    """A habit action cannot run. Messages are for the user."""


@dataclass(frozen=True)
class Habit:
    id: str
    name: str
    area: str
    every: str  # 'day' or 'week'
    times: int  # practices a week; 1 when every == 'day'
    unit: str
    goal: Optional[Decimal]
    reminder: bool
    active: bool


@dataclass(frozen=True)
class Streak:
    current: int  # days in a row (every == 'day') or weeks in a row (every == 'week')
    longest: int
    done_this_week: int
    target_week: int
    done_today: bool


def plural(count: int, one: str, many: str) -> str:
    """'1 giorno', '3 giorni'."""
    return f"{count} {one if count == 1 else many}"


def run_text(every: str, count: int) -> str:
    """'1 giorno di fila', '5 settimane di fila'."""
    return plural(count, *(("settimana", "settimane") if every == "week" else ("giorno", "giorni"))) + " di fila"


def _decimal(value: Any) -> Optional[Decimal]:
    return None if value is None else Decimal(str(value))


def _template_check(store: Any, *slugs: str) -> None:
    for slug in slugs:
        if store.find_template(slug) is None:
            raise HabitError(f"manca il modello '{slug}': installa la Scuola «Askesis · Abitudini» (`zbone pack install {PACK_NAME}`)")


def _habit(entry: Any, template: Any) -> Habit:
    values: Mapping[str, Any] = entry.values
    weekly = values.get("ogni") == WEEKLY
    times = min(7, max(1, int(values.get("volte") or DEFAULT_TIMES))) if weekly else 1
    return Habit(
        id=entry.id,
        name=str(values.get("nome") or "").strip(),
        area=entry.area or template.area,
        every="week" if weekly else "day",
        times=times,
        unit=str(values.get("unita") or "").strip(),
        goal=_decimal(values.get("traguardo")),
        reminder=values.get("promemoria") == "Sì",
        active=values.get("attivo") != "No",
    )


def load_habits(store: Any, include_inactive: bool = False) -> List[Habit]:
    if store.find_template(HABIT) is None:
        return []
    template = store.get_template(HABIT)
    habits = [_habit(entry, template) for entry in store.list_entries(template=HABIT, newest_first=False)]
    return [habit for habit in habits if include_inactive or habit.active]


def _practice_entries(store: Any, habit_id: str) -> List[Any]:
    if store.find_template(PRACTICE) is None:
        return []
    return [entry for entry in store.list_entries(template=PRACTICE, newest_first=False) if habit_id in (entry.values.get("rituale") or [])]


def practices_of(store: Any, habit_id: str) -> Dict[date, Optional[Decimal]]:
    """Day → quantity (None when only «done» was marked). Should a day hold two practices, the later one wins."""
    return {date.fromisoformat(entry.day): _decimal(entry.values.get("quantita")) for entry in _practice_entries(store, habit_id)}


# * — streaks —


def _counts(habit: Habit, practices: Mapping[date, Optional[Decimal]]) -> Set[date]:
    """The days that count: any practice, or one that reaches the goal when the habit has one."""
    return {day for day, quantity in practices.items() if habit.goal is None or (quantity is not None and quantity >= habit.goal)}


def _monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _week_runs(weeks: Set[date], this_week: date) -> tuple:
    """(current, longest) runs of consecutive weeks. The week in progress is open: it only adds when it is already full."""
    current = 0
    cursor = this_week if this_week in weeks else this_week - timedelta(weeks=1)
    while cursor in weeks:
        current += 1
        cursor -= timedelta(weeks=1)
    longest = run = 0
    previous: Optional[date] = None
    for week in sorted(week for week in weeks if week <= this_week):
        run = run + 1 if previous is not None and week - previous == timedelta(weeks=1) else 1
        longest = max(longest, run)
        previous = week
    return current, longest


def streak(habit: Habit, practices: Mapping[date, Optional[Decimal]], today: date) -> Streak:
    days = {day for day in _counts(habit, practices) if day <= today}
    this_week = _monday(today)
    done_this_week = sum(1 for day in days if _monday(day) == this_week)
    if habit.every == "day":
        current, longest = streaks(days, today)
        target = 7
    else:
        per_week: Dict[date, int] = {}
        for day in days:
            per_week[_monday(day)] = per_week.get(_monday(day), 0) + 1
        current, longest = _week_runs({week for week, count in per_week.items() if count >= habit.times}, this_week)
        target = habit.times
    return Streak(current, longest, done_this_week, target, today in days)


def due_today(habits: Sequence[Habit], practices_by_habit: Mapping[str, Mapping[date, Optional[Decimal]]], today: date) -> List[Habit]:
    """The active habits not yet done today."""
    return [habit for habit in habits if habit.active and today not in _counts(habit, practices_by_habit.get(habit.id, {}))]


def find_habit(habits: Sequence[Habit], text: str) -> Habit:
    """By the first letters of the name; an exact name wins; more than one match is an error that lists them."""
    wanted = " ".join(text.lower().split())
    exact = [habit for habit in habits if habit.name.lower() == wanted]
    found = exact or [habit for habit in habits if wanted and habit.name.lower().startswith(wanted)]
    if not found:
        raise HabitError(f"nessun rituale che inizia con «{text.strip()}»")
    if len(found) > 1:
        raise HabitError(f"«{text.strip()}» può essere più di un rituale: " + ", ".join(habit.name for habit in found))
    return found[0]


# * — marking —


def _quantity(quantity: Any) -> Optional[Decimal]:
    if quantity is None or quantity == "":
        return None
    try:
        value = Decimal(quantity.strip().replace(",", ".")) if isinstance(quantity, str) else Decimal(str(quantity))
    except InvalidOperation:
        raise HabitError("quantità non valida") from None
    if not value.is_finite() or value < 0:
        raise HabitError("quantità non valida")
    return value


def _stored(value: Decimal) -> Any:
    return int(value) if value == value.to_integral_value() else float(value)


def _check_habit(store: Any, habit_id: str) -> Any:
    _template_check(store, HABIT, PRACTICE)
    try:
        entry = store.get_entry(habit_id)
    except StoreError as error:
        raise HabitError(str(error)) from None
    if entry.template != HABIT:
        raise HabitError("questa voce non è un rituale")
    return entry


def mark(store: Any, habit_id: str, day: date, quantity: Any = None) -> Any:
    """Mark the habit done on `day`, or change that day's practice (one a day). Marking again without a quantity keeps the old one."""
    habit = _check_habit(store, habit_id)
    if day > date.today():
        raise HabitError("giorno nel futuro: si segna solo ciò che è già successo")
    amount = _quantity(quantity)
    values: Dict[str, Any] = {} if amount is None else {"quantita": _stored(amount)}
    existing = [entry for entry in _practice_entries(store, habit.id) if entry.day == day.isoformat()]
    if existing:
        return store.update_entry(existing[-1].id, values)
    return store.add_entry(PRACTICE, {"rituale": [habit.id], **values}, day=day.isoformat(), area=habit.area or None)


def unmark(store: Any, habit_id: str, day: date) -> bool:
    """Remove the practice of that day. False when there was none."""
    _check_habit(store, habit_id)
    found = [entry for entry in _practice_entries(store, habit_id) if entry.day == day.isoformat()]
    for entry in found:
        store.delete_entry(entry.id)
    return bool(found)
