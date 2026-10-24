"""0.2.8: birthdays coming up (`people.occasions`) and the open goals of every area (`areas.goals_overview`)."""

from datetime import date, timedelta

import pytest
from typer.testing import CliRunner

from zibaldone.cli.app import app
from zibaldone.core import areas as A
from zibaldone.core import people as P
from zibaldone.core.packs import apply_install, find_builtin_pack, plan_install
from zibaldone.core.privacy import NOTICE_VERSION
from zibaldone.storage.database import Store
from zibaldone.storage.paths import data_dir
from zibaldone.storage.settings import record_consent

runner = CliRunner()


def install(store: Store, *names: str) -> None:
    for name in names:
        apply_install(plan_install(find_builtin_pack(name), store), store)


@pytest.fixture
def store(isolated_data_dir):
    with Store.open(isolated_data_dir) as opened:
        install(opened, "persone", "aree")
        yield opened


def people_with(store: Store, **birthdays: str) -> list:
    for name, birthday in birthdays.items():
        store.add_entry("persona", {"nome": name, "compleanno": birthday} if birthday else {"nome": name})
    return P.load_people(store)


def test_birthday_today_soon_and_far(store) -> None:
    today = date(2026, 10, 24)
    found = P.occasions(people_with(store, Marco="1986-10-24", Lia="1990-10-26", Gino="1950-12-31", Nina="2000-09-01", Senza=""), today)
    assert [(item.name, item.in_days, item.turning) for item in found] == [("Marco", 0, 40), ("Lia", 2, 36)]
    assert found[0].kind == "compleanno" and found[0].day == today and found[1].day == date(2026, 10, 26)
    assert [item.name for item in P.occasions(people_with(store), today, days=90)] == ["Marco", "Lia", "Gino"]  # Gino is 68 days away


def test_birthday_across_the_new_year_and_the_29th_of_february(store) -> None:
    people = people_with(store, Bea="1980-01-03", Leo="2000-02-29", Zoe="2026-12-30")
    december = P.occasions(people, date(2026, 12, 28), days=10)
    assert [(item.name, item.day, item.in_days, item.turning) for item in december] == [("Zoe", date(2026, 12, 30), 2, None), ("Bea", date(2027, 1, 3), 6, 47)]  # born this year: no age to show
    assert [(item.day, item.turning) for item in P.occasions(people, date(2027, 2, 20), days=10) if item.name == "Leo"] == [(date(2027, 2, 28), 27)]  # not a leap year: the 28th
    assert [(item.day, item.in_days) for item in P.occasions(people, date(2028, 2, 20), days=10) if item.name == "Leo"] == [(date(2028, 2, 29), 9)]
    assert [item.name for item in P.occasions(people, date(2026, 12, 28), days=-1)] == []


def goal(store: Store, title: str, **values) -> None:
    area = values.pop("area", None)
    store.add_entry("obiettivo", {"titolo": title, **values}, day="2026-10-01", area=area)


def test_goals_overview_sorted_by_deadline_with_open_ones_only(store) -> None:
    today = date(2026, 10, 24)
    goal(store, "Senza scadenza", area="studio")
    goal(store, "Tardi", scadenza="2026-12-01", area="salute")
    goal(store, "Presto", scadenza="2026-10-30", area="lavoro", stato={"status": "ongoing", "current": 1, "total": 4})
    goal(store, "Scaduto", scadenza="2026-10-20", area="salute")
    goal(store, "Fatto", scadenza="2026-10-25", area="salute", stato={"status": "completed"})
    lines = A.goals_overview(store, today)
    assert [(line.goal.title, line.area, line.days_left) for line in lines] == [("Scaduto", "salute", -4), ("Presto", "lavoro", 6), ("Tardi", "salute", 38), ("Senza scadenza", "studio", None)]
    assert lines[1].goal.percent == 25
    assert [line.goal.title for line in A.goals_overview(store, today, "Salute")] == ["Scaduto", "Tardi"]
    with pytest.raises(ValueError, match="area sconosciuta"):
        A.goals_overview(store, today, "marte")


def test_goals_without_any_area_still_show(store) -> None:
    goal(store, "Senza area")
    assert [(line.goal.title, line.area) for line in A.goals_overview(store, date(2026, 10, 24))] == [("Senza area", "")]


def test_cli_occasions_and_goals(isolated_data_dir) -> None:
    record_consent(data_dir(), accepted=True, notice_version=NOTICE_VERSION)
    today = date.today()
    with Store.open(data_dir()) as opened:
        install(opened, "persone", "aree")
        opened.add_entry("persona", {"nome": "Marco", "compleanno": f"1986-{today.month:02d}-{today.day:02d}" if (today.month, today.day) != (2, 29) else "1986-02-28"})
        opened.add_entry("obiettivo", {"titolo": "Correre 10 km", "scadenza": (today + timedelta(days=9)).isoformat()}, area="salute")
        opened.add_entry("obiettivo", {"titolo": "Leggere di più"}, area="svago")
    shown = runner.invoke(app, ["ricorrenze"])
    assert shown.exit_code == 0 and "Marco · compleanno" in shown.output, shown.output
    assert "Nessuna ricorrenza nei prossimi 0 giorni" not in shown.output and runner.invoke(app, ["ricorrenze", "--giorni", "-1"]).exit_code == 1
    listed = runner.invoke(app, ["area", "obiettivi"])
    assert listed.exit_code == 0 and listed.output.index("Correre 10 km") < listed.output.index("Leggere di più") and "9 giorni alla scadenza" in listed.output, listed.output
    one = runner.invoke(app, ["area", "obiettivi", "svago"])
    assert "Leggere di più" in one.output and "Correre" not in one.output
    assert "Nessun obiettivo aperto." in runner.invoke(app, ["area", "obiettivi", "lavoro"]).output
    assert runner.invoke(app, ["area", "obiettivi", "marte"]).exit_code == 1
