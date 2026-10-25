"""«La tua home» (0.3.0): the tiles of Oggi on a grid, kept in home.json."""

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


def P(key, col, row, w, h):
    return H.Placement(key, col, row, w, h)


def keys(layout):
    return [p.key for p in layout]


def cells(layout):
    return [(col, row) for p in layout for col in range(p.col, p.col + p.w) for row in range(p.row, p.row + p.h)]


def test_default_layout_has_every_base_tile_inside_the_grid_without_overlap() -> None:
    layout = H.default_layout()
    assert keys(layout) == list(H.TILES) and H.validate(layout) == layout
    assert len(cells(layout)) == len(set(cells(layout)))
    assert H.default_layout(["abc"]) == layout and H.hidden(layout, ["abc"]) == ["vista:abc"]


def test_validate_drops_the_unknown_the_repeated_the_outside_and_the_overlapping_and_forces_limits() -> None:
    layout = [P("aree", 0, 0, 5, 1), P("boh", 0, 1, 1, 1), P("aree", 0, 2, 1, 1), P("citazione", 4, 1, 3, 1), P("bilancio", 0, 0, 2, 1), P("abitudini", 0, 1, 9, 9), P("vista:x", 0, 5, 3, 1)]
    assert H.validate(layout) == [P("aree", 0, 0, 5, 1), P("abitudini", 0, 1, 5, 3), P("vista:x", 0, 5, 3, 1)]
    assert H.validate([P("abitudini", 0, 0, 0, 0)]) == [P("abitudini", 0, 0, 1, 1)]
    assert H.validate([P("vista:x", 0, 0, 5, 9)]) == [P("vista:x", 0, 0, 5, 3)]
    assert H.validate([P("aree", -1, 0, 1, 1), "no", None]) == []


def test_place_moves_resizes_adds_and_refuses_in_italian() -> None:
    layout = H.default_layout()
    moved = H.place(layout, "bilancio", 3, 5)
    assert next(p for p in moved if p.key == "bilancio") == P("bilancio", 3, 5, 2, 1) and len(moved) == len(layout) and layout == H.default_layout()
    assert H.place(H.remove(layout, "bilancio"), "bilancio", 3, 5, 1, 1)[-1] == P("bilancio", 3, 5, 1, 1)
    assert H.place(layout, "vista:x", 0, 5, 5, 1)[-1] == P("vista:x", 0, 5, 5, 1)
    for call, text in (
        (lambda: H.place(layout, "boh", 0, 0), "sconosciuto"),
        (lambda: H.place(layout, "aree", 1, 0), "esce dalla griglia"),
        (lambda: H.place(layout, "aree", 0, 6), "esce dalla griglia"),
        (lambda: H.place(layout, "aree", -1, 0), "esce dalla griglia"),
        (lambda: H.place(layout, "aree", 0, 0, 5, 4), "alto da 1 a 3"),
        (lambda: H.place(layout, "aree", 0, 0, 0, 1), "largo da 1 a 5"),
        (lambda: H.place(layout, "bilancio", 0, 0), "sopra «promemoria»"),
    ):
        with pytest.raises(H.HomeError, match=text):
            call()


def test_remove_and_hidden() -> None:
    layout = H.default_layout()
    smaller = H.remove(layout, "citazione")
    assert H.hidden(smaller) == ["citazione"] and H.hidden(smaller, ["a"]) == ["citazione", "vista:a"]
    for call in (lambda: H.remove(layout, "vista:a"), lambda: H.remove([P("aree", 0, 0, 5, 1)], "aree")):
        with pytest.raises(H.HomeError):
            call()


def test_compact_slides_up_then_left_keeping_the_reading_order() -> None:
    tidy = H.compact([P("aree", 2, 3, 3, 1), P("citazione", 0, 5, 5, 1), P("bilancio", 4, 1, 1, 2)])
    assert {p.key: (p.col, p.row) for p in tidy} == {"bilancio": (0, 0), "aree": (1, 0), "citazione": (0, 2)}
    assert H.validate(tidy) == tidy and H.compact(tidy) == tidy and H.compact(H.default_layout()) == H.default_layout() and H.compact([]) == []


def test_from_list_stacks_in_order_and_leaves_out_what_does_not_fit() -> None:
    assert H.from_list(list(H.TILES)) == H.default_layout()
    stacked = H.from_list(["aree", "boh", "aree", 7, "vista:a", "vista:b", "vista:c"])
    assert keys(stacked) == ["aree", "vista:a", "vista:b"]  # a third 5x2 view has no room left
    assert H.validate(stacked) == stacked and H.from_list([]) == []


def test_no_file_a_broken_file_or_nothing_valid_gives_the_default(tmp_path) -> None:
    assert home_log.load_layout(tmp_path) == H.default_layout()
    home_log.home_path(tmp_path).write_text("{non json", encoding="utf-8")
    assert home_log.load_layout(tmp_path) == H.default_layout()
    for text in ("[]", '{"versione": 2, "riquadri": "no"}', '{"versione": 2, "riquadri": [{"key": "boh"}, 3]}', '{"tiles": []}', '{"tiles": "aree"}'):
        home_log.home_path(tmp_path).write_text(text, encoding="utf-8")
        assert home_log.load_layout(tmp_path) == H.default_layout(), text
    assert home_log.save_layout(tmp_path, []) == H.default_layout()


def test_the_old_list_file_becomes_a_grid(tmp_path) -> None:
    home_log.home_path(tmp_path).write_text('{"tiles": ["aree", "boh", "aree", 7, "vista:abc", "vista:old", "bilancio"]}', encoding="utf-8")
    assert keys(home_log.load_layout(tmp_path)) == ["aree", "vista:abc", "vista:old", "bilancio"]  # without the list of views, any view key is kept
    assert keys(home_log.load_layout(tmp_path, {"abc"})) == ["aree", "vista:abc", "bilancio"]
    assert home_log.load_layout(tmp_path, {"abc"})[:2] == [P("aree", 0, 0, 5, 1), P("vista:abc", 0, 1, 5, 2)]


def test_round_trip_on_disk_in_format_2_with_no_temporary_file(tmp_path) -> None:
    layout = H.place(H.remove(H.default_layout(), "citazione"), "bilancio", 0, 1, 5, 1)
    assert home_log.save_layout(tmp_path, layout) == layout
    data = json.loads(home_log.home_path(tmp_path).read_text(encoding="utf-8"))
    assert data["versione"] == 2 and data["riquadri"][0] == {"key": "promemoria", "col": 0, "row": 0, "w": 5, "h": 1}
    assert home_log.load_layout(tmp_path) == layout
    assert not list(tmp_path.glob(".home-*"))
    assert home_log.save_layout(tmp_path, [P("aree", 0, 0, 5, 1), P("aree", 0, 1, 1, 1), P("x", 0, 2, 1, 1)]) == [P("aree", 0, 0, 5, 1)]
    home_log.reset_layout(tmp_path)
    home_log.reset_layout(tmp_path)  # twice is fine
    assert home_log.load_layout(tmp_path) == H.default_layout()


def test_a_hand_written_file_with_bad_values_is_cleaned(tmp_path) -> None:
    rows = [{"key": "aree", "col": "0", "row": 0, "w": 5, "h": 1}, {"key": "citazione", "col": 0, "row": 0, "w": 5, "h": 1}, {"key": "bilancio", "col": True, "row": 1, "w": 2.5, "h": 1}, {"key": "abitudini", "col": 0, "row": 1, "w": 3, "h": 1}]
    home_log.home_path(tmp_path).write_text(json.dumps({"versione": 2, "riquadri": rows}), encoding="utf-8")
    assert home_log.load_layout(tmp_path) == [P("citazione", 0, 0, 5, 1), P("abitudini", 0, 1, 3, 1)]


def test_cli_grid_add_move_resize_tidy_remove_and_reset_with_a_view(isolated_data_dir) -> None:
    record_consent(data_dir(), accepted=True, notice_version=NOTICE_VERSION)
    with Store.open(data_dir()) as opened:
        apply_install(plan_install(find_builtin_pack(V.PACK_NAME), opened), opened)
        view = V.save_view(opened, "Libri in corso", text="dune")
    run = lambda *args: runner.invoke(app, ["home", *args])
    shown = run().output
    assert "prome" in shown and "Nascosti: vista:Libri in corso" in shown  # a saved view starts hidden
    assert run("togli", "citazione").exit_code == 0
    assert run("aggiungi", "vista:libri").exit_code == 1  # a 5x2 tile has no room: the free rows are one cell tall
    assert run("ordina").exit_code == 0
    added = run("aggiungi", "vista:libri")
    assert added.exit_code == 0 and "v1 = vista:Libri in corso" in added.output, added.output
    assert home_log.load_layout(data_dir())[-1] == P(f"vista:{view.id}", 0, 4, 5, 2)
    assert run("sposta", "citazione", "1", "1").exit_code == 1  # not in the home
    assert run("sposta", "ricorrenze", "1", "1").exit_code == 1  # on top of promemoria
    assert run("sposta", "ricorrenze", "6", "1").exit_code == 1  # outside the grid
    assert run("ridimensiona", "ricorrenze", "2", "9").exit_code == 1  # past the limits
    assert run("ridimensiona", "ricorrenze", "1", "1").exit_code == 0
    assert next(p for p in home_log.load_layout(data_dir()) if p.key == "ricorrenze") == P("ricorrenze", 3, 2, 1, 1)
    assert run("sposta", "ricorrenze", "5", "3").exit_code == 0
    assert next(p for p in home_log.load_layout(data_dir()) if p.key == "ricorrenze") == P("ricorrenze", 4, 2, 1, 1)
    assert run("aggiungi", "citazione", "1", "6").exit_code == 1  # row 6 is taken by the view
    assert run("aggiungi", "citazione", "1", "4").exit_code == 1  # on top of obiettivi
    assert run("aggiungi", "boh").exit_code == 1
    assert run("togli", "vista:libri").exit_code == 0 and "Nascosti: citazione, vista:Libri in corso" in run().output
    assert run("ripristina").exit_code == 0 and home_log.load_layout(data_dir()) == H.default_layout()
    home_log.save_layout(data_dir(), H.place(H.default_layout(), f"vista:{view.id}", 0, 5, 5, 1))
    assert "v1 = vista:Libri in corso" in run().output
    assert runner.invoke(app, ["viste", "togli", "libri"]).exit_code == 0
    assert "vista:" not in run().output  # the view is gone: its tile too
