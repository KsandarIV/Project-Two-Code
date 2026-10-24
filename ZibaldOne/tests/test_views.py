"""Theoria (0.2.8): saved searches, with a filter on one block and no peeking at secrets."""

import pytest
from typer.testing import CliRunner

from zibaldone.cli.app import app
from zibaldone.core import views as V
from zibaldone.core.crypto import ScryptParams
from zibaldone.core.packs import apply_install, find_builtin_pack, plan_install
from zibaldone.core.privacy import NOTICE_VERSION
from zibaldone.storage import keys
from zibaldone.storage.database import Store
from zibaldone.storage.paths import data_dir
from zibaldone.storage.settings import record_consent

runner = CliRunner()


@pytest.fixture(autouse=True)
def fast_scrypt(monkeypatch):
    monkeypatch.setattr(keys, "DEFAULT_SCRYPT_PARAMS", ScryptParams(n=2**10))
    monkeypatch.setattr(keys, "PIN_SCRYPT_PARAMS", ScryptParams(n=2**10))


def install(store: Store, *names: str) -> None:
    for name in names:
        apply_install(plan_install(find_builtin_pack(name), store), store)


@pytest.fixture
def store(isolated_data_dir):
    with Store.open(isolated_data_dir) as opened:
        install(opened, "collezioni", V.PACK_NAME)
        opened.add_entry("libro", {"titolo": "Dune", "stato": {"status": "ongoing"}}, day="2026-10-01")
        opened.add_entry("libro", {"titolo": "Emma", "stato": {"status": "completed"}}, day="2026-10-05")
        opened.add_entry("libro", {"titolo": "Ivanhoe", "stato": {"status": "ongoing"}}, day="2026-10-09")
        opened.add_entry("film", {"titolo": "Solaris"}, day="2026-10-03")
        yield opened


def titles(entries) -> list:
    return [entry.values["titolo"] for entry in entries]


def test_filter_on_a_block_by_key_or_by_label_and_the_order(store) -> None:
    view = V.save_view(store, "Libri in corso", template="libro", field="stato", value="In corso")
    assert titles(V.run_view(store, view)) == ["Ivanhoe", "Dune"]  # most recent first
    assert titles(V.run_view(store, V.View(view.id, view.name, "libro", "", "", "stato", "ongoing", V.BY_TITLE))) == ["Dune", "Ivanhoe"]
    assert titles(V.run_view(store, view, limit=1)) == ["Ivanhoe"]
    assert V.run_view(store, V.View("x", "n", "libro", "", "", "stato", "Abbandonato", V.RECENT)) == []


def test_text_template_and_area_narrow_the_search(store) -> None:
    assert titles(V.run_view(store, V.View("x", "n", "", "", "dune", "", "", V.RECENT))) == ["Dune"]
    assert sorted(titles(V.run_view(store, V.View("x", "n", "", "svago", "", "", "", V.RECENT)))) == ["Dune", "Emma", "Ivanhoe", "Solaris"]
    assert V.run_view(store, V.View("x", "n", "", "lavoro", "", "", "", V.RECENT)) == []


def test_a_secret_block_is_never_a_filter_or_a_hit(store) -> None:
    keys.setup_keys(data_dir(), "cavallo batteria graffetta")
    install(store, "segreti")
    store.add_entry("diario_segreto", {"testo": "il mio segreto"}, day="2026-10-10")
    assert V.run_view(store, V.View("x", "n", "", "", "segreto", "", "", V.RECENT)) == []  # sealed words are not in the search
    assert V.run_view(store, V.View("x", "n", "diario_segreto", "", "", "testo", "il mio segreto", V.RECENT)) == []
    assert len(V.run_view(store, V.View("x", "n", "diario_segreto", "", "", "", "", V.RECENT))) == 1  # the entry itself is listed, sealed


def test_save_checks_the_filters_and_find_view_takes_first_letters(store) -> None:
    for wrong, message in (
        (dict(name=" "), "nome"),
        (dict(name="a", template="nonesiste"), "nessun modello"),
        (dict(name="a", area="marte"), "area sconosciuta"),
        (dict(name="a", field="stato"), "campo e il valore"),
        (dict(name="a", template="libro", field="boh", value="x"), "non ha un blocco"),
        (dict(name="a", order="Casuale"), "ordine"),
    ):
        with pytest.raises(V.ViewError, match=message):
            V.save_view(store, **wrong)
    first = V.save_view(store, "Libri in corso", template="libro")
    V.save_view(store, "Libri letti", template="libro")
    with pytest.raises(V.ViewError, match="esiste già"):
        V.save_view(store, "libri IN corso")
    views = V.load_views(store)
    assert V.find_view(views, "libri in").id == first.id
    with pytest.raises(V.ViewError, match="Libri in corso, Libri letti"):
        V.find_view(views, "libri")
    assert V.delete_view(store, first.id) is True and V.delete_view(store, first.id) is False
    assert V.delete_view(store, store.list_entries(template="libro")[0].id) is False  # not a view: nothing is deleted
    assert store.count_entries("libro") == 3


def test_without_the_pack_a_message_says_how_to_install_it(isolated_data_dir) -> None:
    with Store.open(isolated_data_dir) as bare:
        assert V.load_views(bare) == []
        with pytest.raises(V.ViewError, match="zbone pack install theoria"):
            V.save_view(bare, "x")


def test_cli_save_show_and_remove(isolated_data_dir) -> None:
    record_consent(data_dir(), accepted=True, notice_version=NOTICE_VERSION)
    assert runner.invoke(app, ["viste"]).exit_code == 1  # no pack yet
    with Store.open(data_dir()) as opened:
        install(opened, "collezioni", V.PACK_NAME)
        opened.add_entry("libro", {"titolo": "Dune", "stato": {"status": "ongoing"}})
        opened.add_entry("libro", {"titolo": "Emma", "stato": {"status": "completed"}})
    assert "Nessuna vista" in runner.invoke(app, ["viste"]).output
    assert runner.invoke(app, ["viste", "salva", "In corso", "--modello", "libro", "--campo", "stato"]).exit_code == 1  # CAMPO=VALORE
    saved = runner.invoke(app, ["viste", "salva", "In corso", "--modello", "libro", "--campo", "stato=In corso"])
    assert saved.exit_code == 0 and "salvata" in saved.output, saved.output
    shown = runner.invoke(app, ["viste", "mostra", "in c"])
    assert shown.exit_code == 0 and "Dune" in shown.output and "Emma" not in shown.output, shown.output
    assert "stato = In corso" in runner.invoke(app, ["viste"]).output
    assert runner.invoke(app, ["viste", "mostra", "zzz"]).exit_code == 1
    assert "tolta" in runner.invoke(app, ["viste", "togli", "in corso"]).output
    assert "Nessuna vista" in runner.invoke(app, ["viste"]).output
