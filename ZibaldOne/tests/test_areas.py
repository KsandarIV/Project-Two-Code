"""Eudaimonia, the 8 life areas (0.2.0): core rules, storage, migration and CLI."""

import json
import re
import sqlite3
from datetime import date, timedelta

import pytest
from typer.testing import CliRunner

from zibaldone import __version__
from zibaldone.cli.app import app
from zibaldone.core import areas as A
from zibaldone.core.brand import AREAS
from zibaldone.core.packs import apply_install, find_builtin_pack, plan_install
from zibaldone.core.privacy import NOTICE_VERSION
from zibaldone.core.templates import BlockSpec, Entry, Template
from zibaldone.storage.database import MIGRATIONS, Store, database_path
from zibaldone.storage.paths import data_dir
from zibaldone.storage.settings import record_consent

TODAY = date(2026, 10, 17)
runner = CliRunner()


def day(offset: int, base: date = TODAY) -> str:
    return (base - timedelta(days=offset)).isoformat()


def install(store: Store, *names: str) -> None:
    for name in names:
        apply_install(plan_install(find_builtin_pack(name), store), store)


@pytest.fixture
def store(isolated_data_dir):
    with Store.open(isolated_data_dir) as opened:
        install(opened, "diario", "aree", "persone", "collezioni", "io")
        yield opened


def load(store: Store):
    return store.list_entries(newest_first=False), {template.slug: template for template in store.list_templates()}


# * — the 8 areas —


def test_the_areas_have_mascots_and_known_spellings() -> None:
    assert [area.key for area in A.AREA_LIST] == AREAS
    assert all(area.mascot is not None and area.color.startswith("#") for area in A.AREA_LIST)
    assert A.find_area("Salute") == "salute" and A.find_area("  SVAGO ") == "svago"
    assert A.find_area("Health") == "salute" and A.find_area("education") == "studio"  # names of the old Journal App
    assert A.find_area("Tempo libero") == "svago" and A.find_area("pippo") is None and A.find_area(3) is None
    with pytest.raises(ValueError, match="area sconosciuta: 'pippo'. Le aree sono: personale"):
        A.parse_area("pippo")


def test_templates_and_entries_carry_an_area() -> None:
    template = Template("corsa", "Corsa", [BlockSpec("km", "number", "Km")], area="Salute").validate()
    assert template.area == "salute" and template.to_dict()["area"] == "salute"
    assert Template.from_dict(template.to_dict()).area == "salute"
    with pytest.raises(ValueError, match="area del modello"):
        Template("x", "X", [BlockSpec("a", "text", "A")], area="cucina").validate()
    entry = Entry.new(template, {"km": 5}, "2026-10-01", area="lavoro")
    assert entry.area == "lavoro" and entry.to_dict()["area"] == "lavoro"
    assert "area" not in Entry.new(template, {"km": 5}).to_dict()
    assert A.own_area(entry, template) == "lavoro"
    entry.area = ""
    assert A.own_area(entry, template) == "salute" and A.entry_areas(entry, template) == ["salute"]


def test_built_in_templates_belong_to_their_area() -> None:
    packs = {pack.short_name: pack for pack in (find_builtin_pack(name) for name in ("collezioni", "io", "persone", "aree", "diario"))}
    by_slug = {template.slug: template for pack in packs.values() for template in pack.templates}
    assert by_slug["libro"].area == "svago" and by_slug["sport"].area == "salute" and by_slug["identita"].area == "personale"
    assert by_slug["persona"].area == "sociale" and by_slug["sera"].area == ""  # the diary spans every area
    assert {template.slug for template in packs["aree"].templates} == {A.CHECKIN_TEMPLATE, A.GOAL_TEMPLATE, A.TODO_TEMPLATE}


def test_a_person_can_be_in_more_areas(store: Store) -> None:
    marco = store.add_entry("persona", {"nome": "Marco", "aree": ["Famiglia", "lavoro", "boh"]})
    assert store.areas_of(marco.id) == ["famiglia", "lavoro"]  # the template's Sociale is only the fallback
    assert [entry.id for entry in store.list_entries(area="famiglia")] == [marco.id]
    assert store.area_counts() == {"famiglia": 1, "lavoro": 1}


def test_scores_come_from_the_eight_area_check_in_and_the_area_check_in(store: Store) -> None:
    store.add_entry("aree", {"salute": 8, "finanze": 3}, day=day(0))
    store.add_entry("checkin_area", {"punteggio": 6}, day=day(0), area="salute")
    store.add_entry("aree", {"salute": 4}, day=day(40))
    store.add_entry("checkin_area", {"punteggio": 9}, day=day(1))  # no area: it scores nothing
    entries, templates = load(store)
    daily = A.daily_scores(entries, templates, "salute")
    assert daily == {TODAY: 7.0, TODAY - timedelta(days=40): 4.0}
    summary = next(item for item in A.area_overview(entries, templates, TODAY) if item.area.key == "salute")
    assert summary.latest == 7.0 and summary.latest_day == TODAY and summary.average == 7.0 and summary.previous == 4.0
    assert summary.trend == "su" and summary.fraction == pytest.approx(0.7)
    series = A.score_series(daily, TODAY, weeks=4)
    assert len(series) == 4 and series[-1].average == 7.0 and series[-1].end >= TODAY and all(point.average is None for point in series[:-1])
    assert A.score_text(7.0) == "7/10" and A.score_text(6.25) == "6,2/10" and A.score_text(None) == "—"


def test_to_dos_and_goals_of_an_area(store: Store) -> None:
    goal = store.add_entry(
        "obiettivo",
        {"titolo": "Correre 10 km", "stato": {"status": "ongoing", "current": 4, "total": 10}, "scadenza": day(-20), "passi": ["5 km", {"text": "8 km", "done": True}]},
        day=day(3), area="salute",
    )
    store.add_entry("obiettivo", {"titolo": "Vecchio obiettivo", "stato": {"status": "completed"}}, day=day(9), area="salute")
    store.add_entry("sera", {"domani": ["comprare pane"]}, day=day(0))  # the diary is in no area
    A.add_todo(store, "salute", "prenotare il dentista", day=day(2))
    listed = A.add_todo(store, "salute", "  comprare   scarpe ", day=day(1))
    assert listed.values["elenco"][-1] == {"text": "comprare scarpe", "done": False}
    assert len(store.list_entries(template="da_fare")) == 1  # one list per area, filled over time
    entries, templates = load(store)
    todos = A.area_todos(store.list_entries(), templates, "salute")
    assert [todo.text for todo in todos] == ["5 km", "prenotare il dentista", "comprare scarpe"]  # oldest entry first
    assert todos[0].template == "obiettivo" and todos[1].template == "da_fare"
    A.set_todo(store, todos[1], True)
    entries, templates = load(store)
    assert [todo.text for todo in A.area_todos(entries, templates, "salute")] == ["5 km", "comprare scarpe"]
    goals = A.area_goals(entries, templates, "salute")
    assert [item.title for item in goals] == ["Correre 10 km", "Vecchio obiettivo"]
    assert goals[0].entry_id == goal.id and goals[0].active and goals[0].percent == 40 and goals[0].steps_total == 2 and goals[0].steps_done == 1
    assert not goals[1].active and goals[1].percent == 100
    with pytest.raises(A.AreaError, match="ricarica"):
        A.set_todo(store, A.AreaTodo("non c'è", todos[1].entry_id, "elenco", 0, TODAY, ""), True)
    with pytest.raises(A.AreaError, match="scrivi che cosa"):
        A.add_todo(store, "salute", "   ")


def test_area_detail_and_check_in(store: Store) -> None:
    A.check_in(store, "Lavoro", 5, good="il progetto", better="le riunioni", day=day(0))
    store.add_entry("riflessione", {"titolo": "Il capo", "testo": "..."}, day=day(1), area="lavoro")
    store.add_entry("libro", {"titolo": "Dune"}, day=day(2))
    entries, templates = load(store)
    detail = A.area_detail(entries, templates, "lavoro", TODAY)
    assert detail.area.key == "lavoro" and detail.summary.total == 2 and detail.checkins == 1
    assert [entry.template for entry in detail.recent] == ["checkin_area", "riflessione"]
    assert detail.summary.latest == 5.0 and len(detail.series) == 12
    svago = A.area_detail(entries, templates, "svago", TODAY)
    assert [entry.template for entry in svago.recent] == ["libro"] and "libro" in svago.templates
    with pytest.raises(A.AreaError, match="almeno il punteggio"):
        A.check_in(store, "lavoro")


def test_area_actions_need_the_areas_pack(isolated_data_dir) -> None:
    with Store.open(isolated_data_dir) as bare:
        with pytest.raises(A.AreaError, match="Liceo · Aree"):
            A.add_todo(bare, "salute", "x")
        with pytest.raises(A.AreaError, match="zbone pack install aree"):
            A.check_in(bare, "salute", 3)


def test_coming_soon_is_announced_per_area_and_never_for_a_shipped_version() -> None:
    def parts(version: str):
        return tuple(int(part) for part in version.split("."))

    for item in A.UPCOMING:
        assert all(area in AREAS for area in item.areas), item.title
        if item.version[:1].isdigit():
            assert parts(item.version) > parts(__version__), f"«{item.title}» è già uscito con la {item.version}: toglilo da UPCOMING"
    assert "Maieutica" in [item.title for item in A.upcoming_for()]
    assert A.upcoming_for("personale")[0].when == "più avanti"


# * — storage —


def test_area_changes_follow_entries_and_templates(store: Store) -> None:
    entry = store.add_entry("riflessione", {"titolo": "Sonno", "testo": "dormo poco"}, area="salute")
    assert [found.id for found in store.list_entries(area="salute")] == [entry.id]
    assert store.search("sonno", area="salute").total == 1 and store.search("sonno", area="studio").total == 0
    store.update_entry(entry.id, {}, area="studio")
    assert store.get_entry(entry.id).area == "studio" and store.list_entries(area="salute") == []
    store.update_entry(entry.id, {"testo": "dormo"})  # area None: unchanged
    assert store.get_entry(entry.id).area == "studio"
    store.update_entry(entry.id, {}, area="")  # back to the template's (none)
    assert store.areas_of(entry.id) == []
    template = store.get_template("riflessione")
    template.area = "personale"
    store.save_template(template, replace=True)
    assert [found.id for found in store.list_entries(area="personale")] == [entry.id]
    with pytest.raises(ValueError):
        store.add_entry("riflessione", {"titolo": "x", "testo": "y"}, area="cucina")
    store.delete_entry(entry.id)
    assert store.area_counts().get("personale") is None


def test_rebuild_keeps_the_areas(store: Store) -> None:
    store.add_entry("libro", {"titolo": "Dune"})
    store.connection.execute("DELETE FROM entry_areas")
    store.connection.commit()
    store.rebuild_indexes()
    assert store.area_counts() == {"svago": 1}


def test_a_schema_2_database_gets_the_areas(isolated_data_dir) -> None:
    path = database_path(isolated_data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path))
    for script in MIGRATIONS[:2]:
        connection.executescript(script)
    book = Template("libro", "Libro", [BlockSpec("titolo", "text", "Titolo")], area="svago").validate()
    connection.execute("INSERT INTO templates VALUES (?, ?, ?, ?)", ("libro", json.dumps(book.to_dict()), "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00"))
    connection.execute(
        "INSERT INTO entries VALUES (?, ?, ?, ?, ?, ?)",
        ("a" * 32, "libro", "2026-01-02", json.dumps({"titolo": "Dune"}), "2026-01-02T00:00:00+00:00", "2026-01-02T00:00:00+00:00"),
    )
    connection.execute("PRAGMA user_version = 2")
    connection.commit()
    connection.close()
    with Store.open(isolated_data_dir) as migrated:
        assert migrated.schema_version == len(MIGRATIONS) == 3
        old = migrated.get_entry("aaaa")
        assert old.area == "" and migrated.areas_of(old.id) == ["svago"]
        assert migrated.area_counts() == {"svago": 1}
        assert migrated.search("dune").total == 1


# * — command line —


@pytest.fixture
def cli_data(isolated_data_dir):
    record_consent(data_dir(), accepted=True, notice_version=NOTICE_VERSION)
    with Store.open(data_dir()) as opened:
        install(opened, "diario", "aree", "persone", "collezioni")
        opened.add_entry("aree", {"salute": 8, "finanze": 3})
        opened.add_entry("sport", {"attivita": "Corsa", "durata": 30})
        opened.add_entry("obiettivo", {"titolo": "Correre 10 km", "passi": ["5 km"]}, area="salute")
    return data_dir()


def invoke(*args: str):
    return runner.invoke(app, list(args))


def test_cli_overview_and_list(cli_data) -> None:
    result = invoke("area")
    assert result.exit_code == 0, result.output
    assert "Eudaimonia · le 8 aree della vita" in result.output and "Diggy" in result.output and "8/10" in result.output
    assert "In arrivo" in result.output and "Maieutica" in result.output
    listed = invoke("area", "list")
    assert "salute" in listed.output and "Diogene di Sinope" in listed.output


def test_cli_check_in_to_do_and_done(cli_data) -> None:
    assert invoke("area", "checkin", "Salute", "--punteggio", "6", "--bene", "cammino").exit_code == 0
    added = invoke("area", "todo", "salute", "prenotare", "il", "dentista")
    assert added.exit_code == 0 and "ora hai 2 cose da fare" in added.output
    shown = invoke("area", "show", "salute")
    assert shown.exit_code == 0, shown.output
    assert "1. 5 km  (Correre 10 km," in shown.output and "2. prenotare il dentista  (" in shown.output
    assert "Correre 10 km · Non iniziato · 0% · 0/1 passi" in shown.output
    done = invoke("area", "fatto", "salute", "2")
    assert done.exit_code == 0 and "Fatto: prenotare il dentista. Ne restano 1." in done.output
    assert invoke("area", "fatto", "salute", "5").exit_code == 1
    unknown = invoke("area", "show", "cucina")
    assert unknown.exit_code == 1 and "area sconosciuta" in unknown.output


def test_cli_entries_templates_and_search_by_area(cli_data) -> None:
    added = invoke("entry", "add", "riflessione", "--set", "titolo=Sonno", "--set", "testo=dormo poco", "--area", "salute")
    assert added.exit_code == 0, added.output
    listed = invoke("entry", "list", "--area", "salute")
    assert "Sonno" in listed.output and "Mens sana" in listed.output and "Esame" not in listed.output
    entry_id = re.search(r"id ([0-9a-f]{8})", added.output).group(1)
    shown = invoke("entry", "show", entry_id)
    assert "Aree: Salute" in shown.output
    assert invoke("entry", "edit", entry_id, "--area", "nessuna").exit_code == 0
    assert "Sonno" not in invoke("entry", "list", "--area", "salute").output
    assert "Aree: Salute (dal modello)" in invoke("entry", "show", invoke("entry", "list", "--template", "sport").output.split()[0]).output
    assert invoke("template", "area", "riflessione", "personale").exit_code == 0
    assert "Area: Personale" in invoke("template", "show", "riflessione").output
    assert "Sonno" in invoke("search", "--area", "personale").output
    assert invoke("entry", "add", "riflessione", "--set", "titolo=X", "--set", "testo=y", "--area", "cucina").exit_code == 1
