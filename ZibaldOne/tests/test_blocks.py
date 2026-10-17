from datetime import date

import pytest

from zibaldone.core.blocks import BLOCK_TYPES, get_block_type, parse_day


def block(name):
    return get_block_type(name)


def test_text_collapses_spaces_and_limits_length() -> None:
    assert block("text").normalize("  Il   nome  della rosa ", {}) == "Il nome della rosa"
    with pytest.raises(ValueError):
        block("text").normalize("x" * 301, {})
    with pytest.raises(ValueError):
        block("text").normalize(42, {})


def test_longtext_keeps_new_lines() -> None:
    assert block("longtext").parse("prima\\nseconda", {}) == "prima\nseconda"


def test_number_parses_italian_decimals_and_checks_bounds() -> None:
    assert block("number").parse("3,5", {}) == 3.5
    assert block("number").parse("12", {"integer": True}) == 12
    with pytest.raises(ValueError):
        block("number").parse("2.5", {"integer": True})
    with pytest.raises(ValueError):
        block("number").normalize(11, {"max": 10})
    with pytest.raises(ValueError):
        block("number").normalize(float("inf"), {})
    with pytest.raises(ValueError):
        block("number").normalize(True, {})


def test_rating_accepts_stars_and_numbers() -> None:
    assert block("rating").parse("***", {}) == 3
    assert block("rating").parse("4", {}) == 4
    assert block("rating").to_text(2, {"max": 5}) == "★★☆☆☆"
    with pytest.raises(ValueError):
        block("rating").parse("6", {})
    with pytest.raises(ValueError):
        block("rating").check_options({"max": 20})


def test_tags_are_lowercase_unique_without_hash() -> None:
    assert block("tags").parse("#Fantasy, fantasy; Tolkien ,", {}) == ["fantasy", "tolkien"]


def test_dates_in_several_formats() -> None:
    assert parse_day("2026-10-17") == "2026-10-17"
    assert parse_day("17/10/2026") == "2026-10-17"
    assert parse_day("oggi") == date.today().isoformat()
    with pytest.raises(ValueError):
        parse_day("2026-02-30")
    with pytest.raises(ValueError):
        parse_day("domani forse")


def test_checklist_parsing() -> None:
    items = block("checklist").parse("[x] spesa; palestra ;  ; [ ] leggere", {})
    assert items == [
        {"text": "spesa", "done": True},
        {"text": "palestra", "done": False},
        {"text": "leggere", "done": False},
    ]
    assert block("checklist").to_text(items[:1], {}) == "[x] spesa"


def test_scale_bounds() -> None:
    assert block("scale").parse("7", {}) == 7
    with pytest.raises(ValueError):
        block("scale").parse("11", {})
    with pytest.raises(ValueError):
        block("scale").check_options({"min": 5, "max": 5})


def test_choice_by_number_prefix_or_name() -> None:
    options = {"choices": ["😄 Ottimo", "🙂 Buono", "😐 Così così"]}
    assert block("choice").parse("2", options) == "🙂 Buono"
    assert block("choice").parse("buo", options) == "🙂 Buono"
    assert block("choice").parse("😐 così così", options) == "😐 Così così"
    with pytest.raises(ValueError):
        block("choice").parse("pessimo", options)
    with pytest.raises(ValueError):
        block("choice").check_options({"choices": ["solo una"]})


def test_progress_parsing_and_completion() -> None:
    assert block("progress").parse("in corso 150/320", {}) == {"status": "ongoing", "current": 150, "total": 320}
    assert block("progress").parse("42", {"total": 100}) == {"status": "ongoing", "current": 42, "total": 100}
    assert block("progress").parse("completato", {"total": 12}) == {"status": "completed", "total": 12, "current": 12}
    assert block("progress").parse("da fare", {}) == {"status": "wishlist"}
    with pytest.raises(ValueError):
        block("progress").parse("400/320", {})
    with pytest.raises(ValueError):
        block("progress").parse("boh", {})
    assert block("progress").to_text({"status": "ongoing", "current": 3, "total": 10}, {"unit": "episodi"}) == "In corso (3/10 episodi)"


def test_link_needs_entry_ids() -> None:
    entry_id = "a" * 32
    assert block("link").normalize(entry_id, {}) == [entry_id]
    with pytest.raises(ValueError):
        block("link").normalize(["marco"], {})
    with pytest.raises(ValueError):
        block("link").normalize([entry_id, "b" * 32], {"multiple": False})


def test_unknown_options_and_types_are_rejected() -> None:
    with pytest.raises(ValueError):
        block("text").check_options({"colore": "rosso"})
    with pytest.raises(ValueError):
        get_block_type("audio")


def test_every_block_has_label_and_description() -> None:
    for name, block_type in BLOCK_TYPES.items():
        assert block_type.name == name
        assert block_type.label and block_type.description
