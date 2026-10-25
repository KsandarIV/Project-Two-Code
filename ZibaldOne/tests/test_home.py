"""«La tua home» (0.2.8): the tiles of Oggi, kept in home.json."""

import json

import pytest
from typer.testing import CliRunner

from zibaldone.cli.app import app
from zibaldone.core import home as H
from zibaldone.core import views as V
from zibaldone.core.packs import apply_install, find_builtin_pack, plan_install
from zibaldone.core.privacy import NOTICE_VERSION
from zibaldone.storage import home_log
from zibaldone.storage.database import Store
from zibaldone.storage.paths import data_dir
from zibaldone.storage.settings import record_consent

runner = CliRunner()


def test_no_file_a_broken_file_or_an_empty_layout_give_the_default(tmp_path) -> None:
    assert home_log.load_layout(tmp_path) == list(H.DEFAULT_LAYOUT) == list(H.TILES)
    home_log.home_path(tmp_path).write_text("{non json", encoding="utf-8")
    assert home_log.load_layout(tmp_path) == list(H.DEFAULT_LAYOUT)
    home_log.save_layout(tmp_path, [])
    assert home_log.load_layout(tmp_path) == list(H.DEFAULT_LAYOUT)


def test_unknown_keys_repeats_and_deleted_views_are_dropped(tmp_path) -> None:
    home_log.home_path(tmp_path).write_text('{"tiles": ["aree", "boh", "aree", 7, "vista:abc", "vista:old", "vista:", "bilancio"]}', encoding="utf-8")
    assert home_log.load_layout(tmp_path) == ["aree", "vista:abc", "vista:old", "bilancio"]  # without the list of views, any view key is kept
    assert home_log.load_layout(tmp_path, {"abc"}) == ["aree", "vista:abc", "bilancio"]
    assert home_log.save_layout(tmp_path, ["citazione", "x"]) == ["citazione"]
    assert home_log.load_layout(tmp_path) == ["citazione"]
    assert not list(tmp_path.glob(".home-*"))  # no temporary file left
    home_log.reset_layout(tmp_path)
    home_log.reset_layout(tmp_path)  # twice is fine
    assert home_log.load_layout(tmp_path) == list(H.DEFAULT_LAYOUT)


def test_add_remove_and_move_tiles() -> None:
    layout = ["aree", "citazione", "bilancio"]
    assert H.add_tile(layout, "abitudini") == [*layout, "abitudini"] and H.add_tile(layout, "aree") == layout and H.add_tile(layout, "vista:1") == [*layout, "vista:1"]
    assert H.move_tile(layout, "bilancio", 1) == ["bilancio", "aree", "citazione"] and H.move_tile(layout, "aree", 99) == ["citazione", "bilancio", "aree"]
    assert H.remove_tile(layout, "citazione") == ["aree", "bilancio"]
    for call in (lambda: H.add_tile(layout, "boh"), lambda: H.remove_tile(layout, "obiettivi"), lambda: H.remove_tile(["aree"], "aree"), lambda: H.move_tile(layout, "obiettivi", 1)):
        with pytest.raises(H.HomeError):
            call()


def test_cli_show_add_move_remove_reset_with_a_view(isolated_data_dir) -> None:
    record_consent(data_dir(), accepted=True, notice_version=NOTICE_VERSION)
    with Store.open(data_dir()) as opened:
        apply_install(plan_install(find_builtin_pack(V.PACK_NAME), opened), opened)
        view = V.save_view(opened, "Libri in corso", text="dune")
    assert "1. promemoria" in runner.invoke(app, ["home"]).output
    assert runner.invoke(app, ["home", "togli", "citazione"]).exit_code == 0
    assert "Nascosti: citazione" in runner.invoke(app, ["home"]).output
    added = runner.invoke(app, ["home", "aggiungi", "vista:libri"])
    assert added.exit_code == 0 and "vista:Libri in corso" in added.output, added.output
    assert home_log.load_layout(data_dir())[-1] == f"vista:{view.id}"
    assert "1. bilancio" in runner.invoke(app, ["home", "sposta", "bilancio"]).output
    assert runner.invoke(app, ["home", "aggiungi", "boh"]).exit_code == 1
    assert runner.invoke(app, ["home", "aggiungi", "vista:zzz"]).exit_code == 1
    V_deleted = runner.invoke(app, ["viste", "togli", "libri"])
    assert V_deleted.exit_code == 0
    assert "vista:" not in runner.invoke(app, ["home"]).output  # the view is gone: its tile too
    assert runner.invoke(app, ["home", "ripristina"]).exit_code == 0
    assert "Nascosti" not in runner.invoke(app, ["home"]).output


def test_a_grid_file_of_0_3_0_is_read_as_a_list_in_reading_order(tmp_path) -> None:
    rows = [{"key": "bilancio", "col": 0, "row": 4, "w": 5, "h": 2}, {"key": "aree", "col": 3, "row": 0, "w": 2, "h": 2}, {"key": "citazione", "col": 0, "row": 0, "w": 3, "h": 2}, {"key": "boh", "col": 0, "row": 9}, "x"]
    home_log.home_path(tmp_path).write_text(json.dumps({"versione": 2, "riquadri": rows}), encoding="utf-8")
    assert home_log.load_layout(tmp_path) == ["citazione", "aree", "bilancio"]
