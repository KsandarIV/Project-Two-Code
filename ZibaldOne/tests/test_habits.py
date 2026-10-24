"""Askesis (0.2.7): habits marked one day at a time; streaks of days or of weeks."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from typer.testing import CliRunner

from zibaldone.cli.app import app
from zibaldone.core import habits as H
from zibaldone.core.packs import apply_install, find_builtin_pack, plan_install
from zibaldone.storage.database import Store
from zibaldone.storage.paths import data_dir
from zibaldone.storage.settings import record_consent
from zibaldone.core.privacy import NOTICE_VERSION

D = Decimal
TODAY = date(2026, 10, 24)  # a Saturday
runner = CliRunner()


def days(*back: int) -> dict:
    return {TODAY - timedelta(days=n): None for n in back}


def habit(**changes) -> H.Habit:
    base = dict(id="h", name="Meditare", area="salute", every="day", times=1, unit="", goal=None, reminder=False, active=True)
    return H.Habit(**{**base, **changes})


@pytest.fixture
def store(isolated_data_dir):
    with Store.open(isolated_data_dir) as opened:
        apply_install(plan_install(find_builtin_pack(H.PACK_NAME), opened), opened)
        yield opened


def test_a_run_of_days_with_a_gap_and_today_still_open() -> None:
    result = H.streak(habit(), days(1, 2, 3, 5, 6, 7, 8), TODAY)  # today not marked yet: it does not break the run
    assert (result.current, result.longest, result.done_today) == (3, 4, False)
    assert H.streak(habit(), days(0, 1, 3), TODAY).current == 2
    assert H.streak(habit(), days(2, 3), TODAY).current == 0  # yesterday missing: the run is over


def test_a_quantity_below_the_goal_does_not_count() -> None:
    water = habit(unit="bicchieri", goal=D(8))
    practices = {TODAY: D(6), TODAY - timedelta(days=1): D(8), TODAY - timedelta(days=2): None, TODAY - timedelta(days=3): D(9)}
    result = H.streak(water, practices, TODAY)
    assert (result.current, result.done_today) == (1, False)  # today 6 of 8 is still open: the run counts from yesterday
    assert H.streak(water, {**practices, TODAY: D(8)}, TODAY).current == 2  # today and yesterday; the day with no quantity breaks it


def test_weekly_habit_counts_weeks_with_enough_practices() -> None:
    run = habit(every="week", times=3)
    week = lambda n, count: {TODAY - timedelta(days=7 * n + k): None for k in range(count)}  # noqa: E731  (TODAY is Saturday: k days back stay in the same week up to 5)
    full_this_week = {**week(0, 3), **week(1, 3), **week(2, 2), **week(3, 3), **week(4, 3)}
    result = H.streak(run, full_this_week, TODAY)
    assert (result.current, result.longest, result.done_this_week, result.target_week) == (2, 2, 3, 3)
    open_week = H.streak(run, {**week(0, 1), **week(1, 3)}, TODAY)  # this week not full yet: it does not break the run
    assert (open_week.current, open_week.done_this_week) == (1, 1)


def test_due_today_skips_done_inactive_and_goal_not_reached() -> None:
    a, b, c = habit(id="a"), habit(id="b", name="Studio", goal=D(2)), habit(id="c", name="Yoga", active=False)
    due = H.due_today([a, b, c], {"a": days(0), "b": {TODAY: D(1)}}, TODAY)
    assert [item.id for item in due] == ["b"]


def test_find_habit_by_first_letters() -> None:
    items = [habit(id="1", name="Meditare"), habit(id="2", name="Movimento"), habit(id="3", name="Acqua")]
    assert H.find_habit(items, "med").id == "1" and H.find_habit(items, "ACQ").id == "3"
    with pytest.raises(H.HabitError, match="Meditare, Movimento"):
        H.find_habit(items, "m")
    with pytest.raises(H.HabitError, match="nessun rituale"):
        H.find_habit(items, "z")


def test_mark_one_practice_per_day_and_unmark(store) -> None:
    ritual = store.add_entry("rituale", {"nome": "Acqua", "unita": "bicchieri", "traguardo": 8})
    first = H.mark(store, ritual.id, date.today(), "5")
    again = H.mark(store, ritual.id, date.today(), "8,5")  # the same day: updated, not doubled
    assert again.id == first.id and store.count_entries("pratica") == 1
    assert H.practices_of(store, ritual.id) == {date.today(): D("8.5")}
    assert H.mark(store, ritual.id, date.today()).id == first.id and H.practices_of(store, ritual.id)[date.today()] == D("8.5")  # no quantity: the old one stays
    assert H.unmark(store, ritual.id, date.today()) is True and H.unmark(store, ritual.id, date.today()) is False
    assert H.practices_of(store, ritual.id) == {}


def test_mark_refuses_future_bad_quantity_and_other_entries(store) -> None:
    ritual = store.add_entry("rituale", {"nome": "Camminare"})
    with pytest.raises(H.HabitError, match="giorno nel futuro"):
        H.mark(store, ritual.id, date.today() + timedelta(days=1))
    for wrong in ("molto", "-2", "nan"):
        with pytest.raises(H.HabitError, match="quantità non valida"):
            H.mark(store, ritual.id, date.today(), wrong)
    practice = H.mark(store, ritual.id, date.today())
    with pytest.raises(H.HabitError, match="non è un rituale"):
        H.mark(store, practice.id, date.today())
    assert store.count_entries("pratica") == 1


def test_load_habits_reads_defaults_and_hides_inactive(store) -> None:
    store.add_entry("rituale", {"nome": "Leggere", "ogni": H.WEEKLY})
    store.add_entry("rituale", {"nome": "Vecchio", "attivo": "No"}, area="studio")
    store.add_entry("rituale", {"nome": "Sera", "ogni": H.WEEKLY, "volte": 5, "promemoria": "Sì", "unita": "minuti", "traguardo": 20}, area="studio")
    shown = {item.name: item for item in H.load_habits(store)}
    assert set(shown) == {"Leggere", "Sera"}
    assert (shown["Leggere"].every, shown["Leggere"].times, shown["Leggere"].area, shown["Leggere"].reminder) == ("week", 3, "salute", False)
    assert (shown["Sera"].times, shown["Sera"].area, shown["Sera"].goal, shown["Sera"].reminder) == (5, "studio", D(20), True)
    assert {item.name for item in H.load_habits(store, include_inactive=True)} == {"Leggere", "Sera", "Vecchio"}


def test_without_the_pack_a_message_says_how_to_install_it(isolated_data_dir) -> None:
    with Store.open(isolated_data_dir) as opened:
        assert H.load_habits(opened) == []
        with pytest.raises(H.HabitError, match="zbone pack install askesis"):
            H.mark(opened, "abcd1234", date.today())


def test_cli_today_mark_series_and_undo(isolated_data_dir) -> None:
    record_consent(data_dir(), accepted=True, notice_version=NOTICE_VERSION)
    assert runner.invoke(app, ["abitudini"]).exit_code == 1  # no pack yet
    with Store.open(data_dir()) as opened:
        apply_install(plan_install(find_builtin_pack(H.PACK_NAME), opened), opened)
        opened.add_entry("rituale", {"nome": "Acqua", "unita": "bicchieri", "traguardo": 8})
        opened.add_entry("rituale", {"nome": "Allungarsi"})
    shown = runner.invoke(app, ["abitudini"])
    assert shown.exit_code == 0 and "Da fare oggi: 2 su 2." in shown.output, shown.output
    ambiguous = runner.invoke(app, ["abitudini", "segna", "a"])
    assert ambiguous.exit_code == 1 and "Acqua, Allungarsi" in ambiguous.output, ambiguous.output
    assert runner.invoke(app, ["abitudini", "segna", "acq", "8"]).exit_code == 0
    assert runner.invoke(app, ["abitudini", "segna", "acq", "8", "--giorno", "domani"]).exit_code == 1
    assert "giorno nel futuro" in runner.invoke(app, ["abitudini", "segna", "acq", "--giorno", (date.today() + timedelta(days=1)).isoformat()]).output
    after = runner.invoke(app, ["abitudini"])
    assert "Da fare oggi: 1 su 2." in after.output and "✓ Acqua" in after.output and "1 giorni di fila" in after.output, after.output
    assert "attuale 1 giorni, la più lunga 1 giorni" in runner.invoke(app, ["abitudini", "serie"]).output
    assert "Tolto «Acqua»" in runner.invoke(app, ["abitudini", "togli", "acq"]).output
    assert "non era segnato" in runner.invoke(app, ["abitudini", "togli", "acq"]).output
