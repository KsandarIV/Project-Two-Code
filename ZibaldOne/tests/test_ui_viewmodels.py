"""What the screens show, computed from a real data folder (no Flet)."""

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from zibaldone.core.packs import apply_install, find_builtin_pack, plan_install
from zibaldone.core.reminders import ReminderConfig
from zibaldone.storage.database import Store
from zibaldone.ui import services
from zibaldone.ui import viewmodels as vm

NOW = datetime(2026, 10, 17, 9, 30)
TODAY = NOW.date()


@pytest.fixture
def folder(isolated_data_dir: Path) -> Path:
    with Store.open(isolated_data_dir) as store:
        for name in ("diario", "collezioni", "persone"):
            apply_install(plan_install(find_builtin_pack(name), store), store)
    return isolated_data_dir


@pytest.fixture
def store(folder: Path):
    with services.open_store(folder) as opened:
        yield opened


def add(store: Store, slug: str, values: dict, day: str = "2026-10-17"):
    return store.add_entry(slug, values, day=day)


def test_today_with_nothing_written(store: Store) -> None:
    model = vm.build_today(store, NOW)
    assert model.date_label == "sabato 17 ottobre 2026"
    assert model.greeting == "Buongiorno"
    assert model.diario_installed
    assert [moment.key for moment in model.moments] == ["mattina", "meta_giornata", "sera"]
    assert not any(moment.written for moment in model.moments)
    assert model.areas.installed and not model.areas.done
    assert len(model.areas.scores) == 8 and all(score.value is None for score in model.areas.scores)
    assert model.entries == ()
    assert model.streak_label == ""


def test_today_after_writing(store: Store) -> None:
    morning = add(store, "mattina", {})
    aree = store.get_template("aree")
    scores = {spec.key: 7 for spec in aree.blocks if spec.type == "scale"}
    add(store, "aree", scores)
    add(store, "sera", {}, day="2026-10-16")
    model = vm.build_today(store, NOW, streak_days=3)
    moments = {moment.key: moment for moment in model.moments}
    assert moments["mattina"].entry_id == morning.id
    assert not moments["sera"].written
    assert model.areas.done
    assert all(score.value == 7 and score.fraction == 0.7 for score in model.areas.scores)
    assert {score.mascot.name for score in model.areas.scores} >= {"Leopy", "Hegy"}
    assert len(model.entries) == 2
    assert model.streak_label == "3 giorni di fila"


def test_entry_list_filters(store: Store) -> None:
    add(store, "libro", {"titolo": "Il nome della rosa"}, day="2026-10-10")
    add(store, "libro", {"titolo": "Le città invisibili"}, day="2026-10-15")
    add(store, "sera", {}, day="2026-10-16")
    rows = vm.list_entry_rows(store, vm.EntryQuery(), TODAY)
    assert [row.day for row in rows] == ["2026-10-16", "2026-10-15", "2026-10-10"]
    assert rows[0].title == store.get_template("sera").name
    assert rows[0].day_label == "ieri"
    assert [row.title for row in vm.list_entry_rows(store, vm.EntryQuery(template="libro"), TODAY)] == ["Le città invisibili", "Il nome della rosa"]
    assert [row.title for row in vm.list_entry_rows(store, vm.EntryQuery(text="citta"), TODAY)] == ["Le città invisibili"]
    add(store, "riflessione", {"titolo": "Appunti", "testo": "Calvino racconta Venezia attraverso altre città."}, day="2026-10-05")
    found = vm.list_entry_rows(store, vm.EntryQuery(text="venezia"), TODAY)
    assert [row.title for row in found] == ["Appunti"] and "Venezia" in found[0].summary  # every block, not only titles
    assert vm.list_entry_rows(store, vm.EntryQuery(text="venezia", template="libro"), TODAY) == []
    reversed_range = vm.EntryQuery(day_from="2026-10-15", day_to="2026-10-11")
    assert [row.day for row in vm.list_entry_rows(store, reversed_range, TODAY)] == ["2026-10-15"]


def test_entry_detail_resolves_links_and_titles(store: Store) -> None:
    giulia = add(store, "persona", {"nome": "Giulia"})
    incontro = store.get_template("incontro")
    link_key = next(spec.key for spec in incontro.blocks if spec.type == "link")
    title_key = incontro.title_key
    meeting = add(store, "incontro", {title_key: "Cena a Trastevere", link_key: [giulia.id]})
    detail = vm.entry_detail(store, meeting.id, TODAY)
    assert detail.title == "Cena a Trastevere" and detail.has_own_title
    assert detail.day_label == "sabato 17 ottobre 2026"
    link_block = next(block for block in detail.blocks if block.type == "link")
    assert link_block.links == ((giulia.id, "Giulia"),)
    untitled = add(store, "sera", {})
    assert not vm.entry_detail(store, untitled.id, TODAY).has_own_title


def test_entry_detail_shows_who_links_and_who_names_it(store: Store) -> None:
    giulia = add(store, "persona", {"nome": "Giulia"})
    incontro = store.get_template("incontro")
    link_key = next(spec.key for spec in incontro.blocks if spec.type == "link")
    add(store, "incontro", {incontro.title_key: "Cena a Trastevere", link_key: [giulia.id]}, day="2026-10-16")
    add(store, "riflessione", {"titolo": "Pensieri", "testo": "Oggi ho chiamato Giulia."}, day="2026-10-15")
    detail = vm.entry_detail(store, giulia.id, TODAY)
    assert [item.title for item in detail.backlinks] == ["Cena a Trastevere"]
    assert "ieri" in detail.backlinks[0].detail and "nel blocco" in detail.backlinks[0].detail
    assert [item.title for item in detail.mentions] == ["Pensieri"] and "Giulia" in detail.mentions[0].excerpt
    assert vm.entry_detail(store, giulia.id, TODAY, mentions=0).mentions == ()


def test_collections_show_progress_and_stars(store: Store) -> None:
    libro = store.get_template("libro")
    progress_key = next(spec.key for spec in libro.blocks if spec.type == "progress")
    rating_key = next(spec.key for spec in libro.blocks if spec.type == "rating")
    add(store, "libro", {libro.title_key: "Le città invisibili", progress_key: {"status": "completed"}, rating_key: 5})
    add(store, "libro", {libro.title_key: "Il nome della rosa", progress_key: {"status": "ongoing", "current": 230, "total": 503}})
    groups = vm.build_collections(store)
    books = groups[0]
    assert books.slug == "libro" and books.count_label == "2 voci"
    first, second = books.items
    assert first.title == "Il nome della rosa" and first.status_label == "In corso"
    assert first.counter.startswith("230/503")
    assert second.fraction == 1.0 and second.rating == 5
    assert all(group.count_label == "nessuna voce" for group in groups[1:])


def test_templates_grouped_by_category(store: Store) -> None:
    counts = {"sera": 2}
    groups = vm.group_templates(store.list_templates(), counts)
    labels = [label for label, _ in groups]
    assert labels[:3] == ["Diario · Stoa", "Collezioni · Museion", "Persone · Agorà"]
    sera = next(row for _, rows in groups for row in rows if row.slug == "sera")
    assert sera.counts_label.endswith("2 voci")
    assert sera.from_pack


def test_editor_round_trip_and_errors(store: Store) -> None:
    libro = store.get_template("libro")
    state = vm.editor_from_template(libro)
    rebuilt = vm.template_from_editor(state, libro.slug)
    assert [spec.key for spec in rebuilt.blocks] == [spec.key for spec in libro.blocks]
    assert [spec.options for spec in rebuilt.blocks] == [spec.options for spec in libro.blocks]
    assert vm.entries_broken_by(store, rebuilt) == 0

    new = vm.EditorState(name="Viaggi", blocks=[vm.new_editor_block("text"), vm.new_editor_block("choice")])
    new.blocks[0].label = "Dove"
    new.blocks[1].label = "Com'era"
    template = vm.template_from_editor(new, "viaggi")
    assert [spec.key for spec in template.blocks] == ["dove", "com_era"]
    assert template.blocks[1].options["choices"] == ["Sì", "No"]

    with pytest.raises(ValueError, match="nome"):
        vm.template_from_editor(vm.EditorState(blocks=[vm.new_editor_block("text")]), "x")
    with pytest.raises(ValueError, match="almeno un blocco"):
        vm.template_from_editor(vm.EditorState(name="Vuoto"), "x")
    bad = vm.EditorState(name="Numeri", blocks=[vm.new_editor_block("rating")])
    bad.blocks[0].label = "Voto"
    bad.blocks[0].options["max"] = "tanti"
    with pytest.raises(ValueError, match="Voto"):
        vm.template_from_editor(bad, "numeri")
    assert vm.move_block(new.blocks, 0, 1)[0].label == "Com'era"
    assert vm.move_block(new.blocks, 0, -1)[0].label == "Dove"
    assert vm.unique_key("Dove", ["dove"]) == "dove_2"


def test_changing_a_template_counts_broken_entries(store: Store) -> None:
    aree = store.get_template("aree")
    add(store, "aree", {aree.blocks[0].key: 9})
    state = vm.editor_from_template(aree)
    state.blocks[0].options["max"] = "5"
    assert vm.entries_broken_by(store, vm.template_from_editor(state, "aree")) == 1


def test_link_blocks_keep_the_core_default_for_multiple(store: Store) -> None:
    incontro = store.get_template("incontro")
    spec = next(spec for spec in incontro.blocks if spec.type == "link")
    block = vm.editor_block_from_spec(spec)
    rebuilt = vm.spec_from_editor(block, [])
    assert bool(rebuilt.options.get("multiple", True)) == bool(spec.options.get("multiple", True))


def test_pack_plan_rows_and_summary(store: Store) -> None:
    io = find_builtin_pack("io")
    card = vm.pack_card(io, [template.slug for template in store.list_templates()])
    assert card.installed_label.endswith("nessuno installato")
    plan = plan_install(io, store)
    assert vm.plan_has_changes(plan)
    assert vm.plan_summary(plan) == f"{len(io.templates)} nuovi"
    assert {row.action_label for row in vm.plan_rows(plan)} == {"nuovo"}
    diario = plan_install(find_builtin_pack("diario"), store)
    assert not vm.plan_has_changes(diario)
    assert "già installati" in vm.plan_summary(diario)


def test_export_writes_only_templates_under_exports(store: Store, folder: Path) -> None:
    add(store, "libro", {"titolo": "Segreto"})
    path = vm.export_templates(store, folder, ["libro", "sera"], "I miei modelli", datetime(2026, 10, 17, 12, 0, 5))
    assert path.parent == folder / "exports"
    assert path.name.endswith("-20261017-120005.zbpack.json")
    text = path.read_text(encoding="utf-8")
    assert "Segreto" not in text
    data = json.loads(text)
    assert data["id"].startswith("personale.")
    with pytest.raises(ValueError, match="almeno un modello"):
        vm.export_templates(store, folder, [], "x", NOW)


def test_reminder_form_round_trip_and_errors() -> None:
    config = ReminderConfig()
    form = vm.reminder_form(config)
    assert vm.config_from_reminder_form(form, config) == config
    form.moments[0].time = "07:15"
    form.moments[0].weekdays = vm.toggle_weekday(form.moments[0].weekdays, 6)
    form.quiet_enabled = False
    changed = vm.config_from_reminder_form(form, config)
    assert changed.moments[0].time == "07:15"
    assert 6 not in changed.moments[0].weekdays
    assert not changed.quiet_hours.enabled
    form.moments[1].time = "25:99"
    with pytest.raises(ValueError):
        vm.config_from_reminder_form(form, config)


@dataclass
class FakeSnapshot:
    id: str
    created_at: datetime
    size: int
    encrypted: bool = False
    reason: str = "manual"
    note: str = ""


def test_snapshot_rows_and_consent_label() -> None:
    rows = vm.snapshot_rows([FakeSnapshot("20261017T100000Z-abc123", datetime(2026, 10, 17, 10, 0, tzinfo=timezone.utc), 2048, True, note="prima")])
    assert rows[0].size == "2.0 KB" and rows[0].encrypted and rows[0].note == "prima"
    assert "2026" in rows[0].when
    assert vm.snapshot_rows([object()])[0].size == "0 B"
    assert vm.consent_label({}) == "non ancora data"
    assert vm.consent_label({"accepted": True, "notice_version": 3, "decided_at": "2026-10-17T10:00:00+00:00"}).startswith("accettata il 17 ott 2026")


def test_picked_dates_come_back_in_local_time() -> None:
    assert vm.picked_date(datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)) == datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc).astimezone().date()
    assert vm.picked_date(date(2026, 10, 17)) == date(2026, 10, 17)
    assert vm.picked_date(None) is None


def test_mascots_include_zibby_for_the_app() -> None:
    cards = vm.mascot_cards()
    assert len(cards) == 9
    assert [card.name for card in cards if card.is_app] == ["Zibby"]


# * — services —


def test_in_app_notifier_queues_messages() -> None:
    notifier = services.InAppNotifier()
    assert notifier.name == "app"
    assert notifier.send("Sera", "Com'è andata oggi?")
    assert [message.title for message in notifier.take()] == ["Sera"]
    assert notifier.take() == []


def test_ui_settings_and_diario_suggestion(isolated_data_dir: Path) -> None:
    folder = isolated_data_dir
    folder.mkdir(parents=True, exist_ok=True)
    assert services.ui_settings(folder) == {}
    assert services.diario_suggestion_pending(folder, [])
    services.save_ui_settings(folder, diario_suggested=True)
    assert services.ui_settings(folder) == {"diario_suggested": True}
    assert not services.diario_suggestion_pending(folder, [])
    assert not services.diario_suggestion_pending(Path(folder / "altro"), ["mattina", "meta_giornata", "sera"])


def test_login_is_not_required_when_the_account_part_is_missing_or_failing(monkeypatch, isolated_data_dir: Path) -> None:
    monkeypatch.setattr(services, "account_api", lambda: None)
    assert services.login_required(isolated_data_dir) is False
    assert services.account_status(isolated_data_dir) == (None, "")

    class Broken:
        @staticmethod
        def login_required(folder):
            raise RuntimeError("rotto")

        @staticmethod
        def account_status(folder):
            raise RuntimeError("rotto")

    monkeypatch.setattr(services, "account_api", lambda: Broken)
    assert services.login_required(isolated_data_dir) is False
    assert services.account_status(isolated_data_dir) == (None, "rotto")


def test_data_folder_inside_an_android_app(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("ZIBALDONE_HOME", raising=False)
    monkeypatch.setenv(services.FLET_DATA_ENV, str(tmp_path / "flet"))
    monkeypatch.setattr(services, "running_on_android", lambda: True)
    assert services.resolve_data_folder() == tmp_path / "flet" / "ZibaldOne"
    monkeypatch.setenv("ZIBALDONE_HOME", str(tmp_path / "scelta"))
    assert services.resolve_data_folder() == tmp_path / "scelta"


def test_streak_and_reminder_config(folder: Path, store: Store) -> None:
    add(store, "sera", {}, day="2026-10-16")
    add(store, "sera", {}, day="2026-10-17")
    assert services.streak_days(store, TODAY) == 2
    config, problem = services.reminder_config(folder)
    assert problem == "" and isinstance(config, ReminderConfig)


def test_graph_drawing_and_taps(store: Store) -> None:
    giulia = add(store, "persona", {"nome": "Giulia"})
    incontro = store.get_template("incontro")
    link_key = next(spec.key for spec in incontro.blocks if spec.type == "link")
    dinner = add(store, "incontro", {incontro.title_key: "Cena a Trastevere", link_key: [giulia.id]})
    add(store, "riflessione", {"titolo": "Pensieri", "testo": "Con [[Giulia]] e [[Bruno]]."})
    graph = vm.load_graph(store, vm.GraphQuery())
    assert vm.graph_summary(graph) == "3 voci, 2 collegamenti"
    drawing = vm.draw_graph(graph, 400, 300)
    assert all(26 <= node.x <= 374 and 26 <= node.y <= 274 for node in drawing.nodes)
    assert len(drawing.edges) == 2 and all(node.label for node in drawing.nodes)  # few nodes: every name is shown
    hub = next(node for node in drawing.nodes if node.id == giulia.id)
    assert hub.radius > next(node for node in drawing.nodes if node.id == dinner.id).radius
    assert vm.nearest_node(drawing, hub.x + 3, hub.y - 2).id == giulia.id
    assert vm.nearest_node(drawing, -500, -500) is None
    waiting = vm.load_graph(store, vm.GraphQuery(unresolved=True))
    assert any(node.kind == "missing" and node.label == "Bruno" for node in waiting.nodes)
    around = vm.load_graph(store, vm.GraphQuery(isolated=False, template="incontro"), around=giulia.id)
    assert {node.id for node in around.nodes} == {giulia.id, dinner.id}
    centered = vm.draw_graph(around, 400, 300, around=giulia.id)
    assert next(node for node in centered.nodes if node.center).id == giulia.id
    assert vm.graph_summary(vm.load_graph(store, vm.GraphQuery(template="libro"))) == "nessuna voce"


def test_stats_periods_and_the_review(store: Store) -> None:
    add(store, "sera", {"umore": "🙂 Buono", "voto": 7, "domani": ["comprare pane"]}, day="2026-10-16")
    add(store, "sera", {"umore": "😐 Così così", "voto": 5}, day="2026-10-14")
    add(store, "libro", {"titolo": "Dune", "stato": {"status": "ongoing", "current": 10, "total": 100}}, day="2026-10-13")
    query = vm.StatsQuery()
    result = vm.load_stats(store, query, TODAY)
    assert result.period.kind == "week" and result.period.contains(TODAY)
    assert vm.writing_line(result) == "3 voci in 3 giorni su 7 (la settimana prima: 0)."
    assert [vm.mood_point_label(point) for point in result.mood_points][:2] == ["lun 12", "mar 13"]
    assert not vm.move_period(query, TODAY, +1)  # never past the current week
    assert vm.move_period(query, TODAY, -1) and query.day == "2026-10-05"
    assert vm.writing_line(vm.load_stats(store, query, TODAY)) == "Nessuna voce in questo periodo."
    assert vm.move_period(query, TODAY, +1) and query.day == ""
    month = vm.load_stats(store, vm.StatsQuery(kind="month"), TODAY)
    assert month.period.label == "ottobre 2026" and vm.mood_point_label(month.mood_points[0]).startswith("sett. ")
    entry, created = vm.prepare_review(store, "week", TODAY, TODAY)
    assert created and entry.template == "settimana" and entry.values["obiettivi"] == [{"text": "comprare pane", "done": False}]
    again, created_again = vm.prepare_review(store, "week", TODAY, TODAY)
    assert again.id == entry.id and not created_again


def test_anonymizer_preview_uses_the_people(store: Store) -> None:
    add(store, "persona", {"nome": "Giulia Bianchi", "soprannomi": ["Giuli"]})
    preview = vm.anonymize_preview(store, "Ieri Giuli mi ha scritto a giulia@example.com, poi ho visto Giulia.", "pseudo")
    assert "Giuli" not in preview.text and "giulia@example.com" not in preview.text
    assert preview.text.count("[PERSONA_1]") == 2 and preview.name_forms >= 3
    kinds = {row.kind for row in preview.rows}
    assert {"nome di persona", "indirizzo email"} <= kinds
    assert vm.anonymize_preview(store, "niente di personale", "anon").rows == ()
    add(store, "riflessione", {"titolo": "Pensieri", "testo": "Parlato con [[Giulia Bianchi]]."})
    assert vm.latest_entry_text(store) == "Pensieri\nParlato con Giulia Bianchi."


def test_night_banner_shows_only_at_night_and_with_pannychis_installed(store: Store) -> None:
    night = vm.build_today(store, datetime(2026, 10, 17, 2, 30))
    assert night.reminder is not None and night.reminder.night
    assert (night.reminder.moment, night.reminder.title) == ("pannychis", "Notti insonni")
    assert vm.build_today(store, datetime(2026, 10, 17, 12, 0)).reminder is None
    assert vm.build_today(store, datetime(2026, 10, 17, 5, 0)).reminder is None
