"""The interface without Flet: theme, navigation and the entry form logic."""

from datetime import date

import pytest

from zibaldone.core.packs import find_builtin_pack
from zibaldone.core.templates import BlockSpec, Entry, Template
from zibaldone.ui import forms
from zibaldone.ui import theme as T
from zibaldone.ui.navigation import (
    HOME,
    SECTIONS,
    SETTINGS_KEYS,
    layout_for,
    parse_route,
    route_path,
    section,
    section_index,
    settings_part,
)


def builtin(slug: str) -> Template:
    for pack_name in ("diario", "collezioni", "io", "persone"):
        pack = find_builtin_pack(pack_name)
        for template in pack.templates:
            if template.slug == slug:
                return template
    raise LookupError(slug)


# * — theme —


def test_text_colours_are_readable_on_the_backgrounds() -> None:
    assert T.contrast_ratio(T.TEXT, T.BG) >= 7
    assert T.contrast_ratio(T.TEXT, T.PANEL) >= 7
    assert T.contrast_ratio(T.TEXT_DIM, T.PANEL) >= 4.5
    assert T.contrast_ratio(T.ACCENT, T.BG) >= 4.5
    assert T.contrast_ratio(T.ERROR, T.PANEL) >= 4.5


def test_readable_on_picks_dark_text_on_bright_fills() -> None:
    assert T.readable_on(T.ACCENT) == T.BG
    assert T.readable_on(T.YELLOW) == T.BG
    assert T.readable_on("#8A2BE2") == T.TEXT
    for color in T.CATEGORICAL:
        assert T.contrast_ratio(T.readable_on(color), color) >= 3


def test_yellow_is_never_used_as_text() -> None:
    assert T.accent_text_color(T.YELLOW) == T.TEXT
    assert T.accent_text_color("#ffff00") == T.TEXT
    assert T.accent_text_color(T.ACCENT) == T.ACCENT


def test_colour_helpers() -> None:
    assert T.color_or("#123456") == "#123456"
    assert T.color_or("rosso") == T.ACCENT
    assert T.color_or("", "#FF5500") == "#FF5500"
    assert T.category_color(0) == T.CATEGORICAL[0]
    assert T.category_color(len(T.CATEGORICAL)) == T.CATEGORICAL[0]
    assert len(T.palette_contrasts(T.CATEGORICAL)) == len(T.CATEGORICAL)
    with pytest.raises(ValueError):
        T.relative_luminance("#12")


# * — navigation —


def test_sections_have_a_plain_and_a_philosophical_name() -> None:
    assert [item.label for item in SECTIONS] == ["Oggi", "Voci", "Collezioni", "Modelli", "Impostazioni"]
    assert section("oggi").nickname == "Hic et nunc"
    assert section("voci").nickname == "Pensieri"
    assert section("modelli").nickname == "Forme"
    assert section("organon").nickname == "Organon"
    assert section_index("modelli") == 3
    assert settings_part("nuvole").nickname == "Le Nuvole"
    assert set(SETTINGS_KEYS) == {"parresia", "daimon", "mnemosyne", "nuvole", "velo", "info"}
    assert settings_part("velo").nickname == "Velo d'ignoranza"


@pytest.mark.parametrize(
    "path, screen, section_key, arg",
    [
        ("/", "oggi", "oggi", ""),
        ("/voci", "voci", "voci", ""),
        ("/voci/abc123", "voce", "voci", "abc123"),
        ("/voci/abc123/modifica", "modifica", "voci", "abc123"),
        ("/scrivi/sera", "scrivi", "", "sera"),
        ("/modelli/nuovo", "modello", "modelli", ""),
        ("/modelli/libro", "modello", "modelli", "libro"),
        ("/scuole", "scuole", "modelli", ""),
        ("/grafo", "grafo", "voci", ""),
        ("/grafo/abc123", "grafo", "voci", "abc123"),
        ("/theoria", "theoria", "oggi", ""),
        ("/organon/daimon", "parte", "organon", "daimon"),
        ("/benvenuto/consenso", "consenso", "", ""),
        ("/benvenuto/copie", "copie", "", ""),
        ("/collezioni?x=1#top", "collezioni", "collezioni", ""),
    ],
)
def test_parse_route(path: str, screen: str, section_key: str, arg: str) -> None:
    route = parse_route(path)
    assert (route.screen, route.section, route.arg) == (screen, section_key, arg)


@pytest.mark.parametrize("path", ["/nulla", "/organon/segreti", "/voci/a/b/c", "/benvenuto/altro", "/grafo/a/b", None, ""])
def test_unknown_routes_go_home(path) -> None:
    assert parse_route(path) == HOME


def test_route_paths_round_trip() -> None:
    for path in ["/oggi", "/voci/x1", "/voci/x1/modifica", "/scrivi/aree", "/modelli/nuovo", "/modelli/sera", "/scuole", "/grafo", "/grafo/x1", "/theoria", "/organon/info", "/benvenuto/diario"]:
        assert parse_route(path).path == path
    assert route_path("modello") == "/modelli/nuovo"
    assert parse_route("/oggi").is_top_level and not parse_route("/voci/x").is_top_level


def test_layout_switches_at_the_breakpoint() -> None:
    assert layout_for(412) == "narrow"
    assert layout_for(T.WIDE_MIN_WIDTH - 1) == "narrow"
    assert layout_for(T.WIDE_MIN_WIDTH) == "wide"
    assert layout_for(1280) == "wide"
    assert layout_for(None) == "wide" and layout_for(0) == "wide"


# * — the entry form —


def test_labels_and_captions() -> None:
    assert forms.type_caption("choice") == "Aut-Aut · Scelta"
    assert forms.type_caption("sconosciuto") == "sconosciuto"
    spec = BlockSpec(key="titolo", type="text", label="Titolo", required=True)
    assert forms.field_label(spec) == "Titolo *"
    assert forms.field_hint(BlockSpec(key="n", type="number", label="N")) == forms.HINTS["number"]
    assert forms.field_hint(BlockSpec(key="s", type="bookmark", label="S", options={"placeholder": "pag. 10"})) == "pag. 10"


def test_numbers_use_the_italian_comma() -> None:
    assert forms.format_number(12) == "12"
    assert forms.format_number(12.5) == "12,5"
    assert forms.format_number(None) == ""
    assert forms.parse_number_text("12,5") == 12.5
    assert forms.parse_number_text(" 7 ") == 7
    assert forms.parse_number_text("") is None
    with pytest.raises(ValueError, match="non è un numero"):
        forms.parse_number_text("dodici", "pagine")


def test_every_block_type_has_an_empty_state_that_collects_to_nothing() -> None:
    from zibaldone.core.blocks import BLOCK_TYPES

    options = {"choice": {"choices": ["Sì", "No"]}}
    blocks = [BlockSpec(key=f"b_{name}", type=name, label=name, options=options.get(name, {})) for name in BLOCK_TYPES]
    template = Template(slug="tutto", name="Tutto", blocks=blocks).validate()
    states = forms.initial_states(template)
    result = forms.collect_values(template, states)
    assert result.ok, result.errors
    assert result.values == {}


def test_sera_form_collects_and_round_trips() -> None:
    sera = builtin("sera")
    states = forms.initial_states(sera)
    choice = next(spec for spec in sera.blocks if spec.type == "choice")
    checklist = next(spec for spec in sera.blocks if spec.type == "checklist")
    scale = next(spec for spec in sera.blocks if spec.type == "scale")
    longtext = next(spec for spec in sera.blocks if spec.type == "longtext")
    states[choice.key] = forms.choice_options(choice)[1]
    states[checklist.key] = forms.checklist_add([], "Palestra\n\n  Leggere   Calvino ")
    states[scale.key] = 8
    states[longtext.key] = "  Una giornata piena.\r\n"
    result = forms.collect_values(sera, states, day="2026-10-16")
    assert result.ok, result.errors
    assert result.day == "2026-10-16"
    assert result.values[checklist.key] == [{"text": "Palestra", "done": False}, {"text": "Leggere Calvino", "done": False}]
    assert result.values[longtext.key] == "Una giornata piena."
    again = forms.initial_states(sera, result.values)
    assert forms.collect_values(sera, again).values == result.values


def test_required_fields_and_errors_go_next_to_their_field() -> None:
    libro = builtin("libro")
    title = next(spec for spec in libro.blocks if spec.required)
    progress = next(spec for spec in libro.blocks if spec.type == "progress")
    states = forms.initial_states(libro)
    states[progress.key] = {"status": "ongoing", "current": "dieci", "total": "300"}
    result = forms.collect_values(libro, states, day="ieri o forse no")
    assert not result.ok
    assert result.errors[title.key] == forms.REQUIRED_MESSAGE
    assert "non è un numero" in result.errors[progress.key]
    assert forms.DAY_KEY in result.errors


def test_scale_rating_and_choice_helpers() -> None:
    aree = builtin("aree")
    personale = aree.blocks[0]
    assert forms.scale_bounds(personale) == (0, 10)
    assert forms.scale_value_text(personale, None) == "non indicato"
    assert forms.scale_value_text(personale, 7) == "7/10"
    low, high = forms.scale_captions_from({"min": 1, "max": 5, "low_label": "poco", "high_label": "tanto"})
    assert (low, high) == ("1 · poco", "5 · tanto")
    assert forms.scale_captions_from({}) == ("0", "10")
    assert forms.toggle_rating(None, 4) == 4
    assert forms.toggle_rating(4, 4) is None
    assert forms.toggle_choice("Sì", "Sì") is None
    assert forms.toggle_choice(None, "No") == "No"
    assert forms.rating_max(BlockSpec(key="v", type="rating", label="Voto", options={"max": 10})) == 10


def test_aree_rejects_out_of_range_scores() -> None:
    aree = builtin("aree")
    states = forms.initial_states(aree)
    states[aree.blocks[0].key] = 11
    result = forms.collect_values(aree, states)
    assert aree.blocks[0].key in result.errors


def test_tags_become_chips_while_typing() -> None:
    tags, rest = forms.absorb_tag_text([], "Mare, #Roma, mon")
    assert (tags, rest) == (["mare", "roma"], "mon")
    tags, rest = forms.absorb_tag_text(tags, "mon", finish=True)
    assert (tags, rest) == (["mare", "roma", "mon"], "")
    tags, _ = forms.absorb_tag_text(tags, "mare,")
    assert tags.count("mare") == 1
    assert forms.remove_tag(tags, "roma") == ["mare", "mon"]
    assert forms.split_tag_text("a, b; c ,") == ["a", "b", "c"]


def test_tag_suggestions_template_first_then_known_without_chosen() -> None:
    spec = BlockSpec(key="generi", type="tags", label="Generi", options={"suggestions": ["giallo", "romanzo", "storico"]})
    assert forms.tag_suggestions(spec, ["saggio", "giallo"], ["romanzo"]) == ["giallo", "storico", "saggio"]
    assert forms.tag_suggestions(spec, ["saggio"], [], prefix="s") == ["storico", "saggio"]
    assert forms.tag_suggestions(spec, [], [], prefix="man") == ["romanzo"]  # contains, after the prefixes
    assert forms.tag_suggestions(spec, [], [], prefix="xyz") == []
    entries = [
        Entry("1", "libro", {"generi": ["giallo", "storico"]}, "2026-10-01", "", ""),
        Entry("2", "libro", {"generi": ["giallo"]}, "2026-10-02", "", ""),
    ]
    assert forms.known_tags(entries, "generi") == ["giallo", "storico"]


def test_checklist_and_progress_helpers() -> None:
    items = forms.checklist_add([{"text": "uno", "done": True}], "due\ntre")
    assert forms.checklist_progress(items) == (1, 3)
    assert forms.progress_fraction({"status": "completed"}) == 1.0
    assert forms.progress_fraction({"status": "ongoing", "current": 50, "total": 200}) == 0.25
    assert forms.progress_fraction({"status": "ongoing"}) is None
    assert forms.progress_fraction(None) is None
    spec = BlockSpec(key="stato", type="progress", label="Stato", options={"total": 26, "unit": "episodi"})
    assert forms.progress_state_fraction(spec, {"status": None, "current": "13", "total": ""}) == 0.5
    assert forms.progress_state_fraction(spec, {"status": None, "current": "tredici", "total": ""}) is None
    assert forms.state_to_raw(spec, forms.empty_state(spec)) is None


def test_entry_titles_and_links() -> None:
    libro = builtin("libro")
    title_key = libro.title_key
    entry = Entry("e1", "libro", {title_key: "Ficciones"}, "2026-10-17", "", "")
    untitled = Entry("e2", "libro", {}, "2026-10-17", "", "")
    assert forms.entry_title(entry, libro) == "Ficciones"
    assert forms.entry_title(untitled, libro) == libro.name
    assert forms.entry_title(untitled, libro, with_day=True) == f"{libro.name} del 17 ott 2026"
    spec = BlockSpec(key="libri", type="link", label="Libri", options={"template": "libro"})
    other = Entry("e3", "sera", {}, "2026-10-17", "", "")
    candidates = forms.link_candidates(spec, [entry, untitled, other], {"libro": libro, "sera": builtin("sera")}, exclude_id="e2")
    assert candidates == [("e1", "Ficciones")]
    assert forms.add_link(["a"], "b", many=True) == ["a", "b"]
    assert forms.add_link(["a"], "a", many=True) == ["a"]
    assert forms.add_link(["a"], "b", many=False) == ["b"]
    assert forms.link_allows_many(BlockSpec(key="l", type="link", label="L"))


def test_italian_dates() -> None:
    from zibaldone.ui import viewmodels as vm

    assert vm.italian_date(date(2026, 10, 17)) == "sabato 17 ottobre 2026"
    assert vm.italian_date(date(2026, 1, 1), weekday=False) == "1 gennaio 2026"
    today = date(2026, 10, 17)
    assert vm.short_date("2026-10-17", today) == "oggi"
    assert vm.short_date("2026-10-16", today) == "ieri"
    assert vm.short_date("2026-10-18", today) == "domani"
    assert vm.short_date("2026-10-01", today) == "1 ott"
    assert vm.short_date("2025-10-01", today) == "1 ott 2025"


def test_a_secret_field_keeps_the_sealed_value_until_changed() -> None:
    spec = BlockSpec.from_dict({"key": "s", "type": "secret", "label": "S", "options": {"multiline": True}})
    sealed = "zbs1:SIGILLATO"
    closed = forms.value_to_state(spec, sealed)
    assert forms.state_to_raw(spec, closed) == sealed  # closed and left empty: unchanged
    assert forms.state_to_raw(spec, {**closed, "text": " nuovo\r\ntesto "}) == "nuovo\ntesto"
    opened = forms.reveal_secret_state(closed, "vecchio")
    assert forms.state_to_raw(spec, opened) == sealed  # opened but not changed: not sealed again
    assert forms.state_to_raw(spec, {**opened, "text": ""}) is None  # opened and emptied: removed
    assert forms.state_to_raw(spec, forms.removed_secret_state()) is None
    assert forms.state_to_raw(spec, forms.empty_state(spec)) is None


def test_a_media_field_keeps_the_attached_files() -> None:
    spec = BlockSpec.from_dict({"key": "f", "type": "media", "label": "F"})
    item = {"file": "a" * 64 + ".jpg", "name": "mare.jpg", "size": 3}
    assert forms.empty_state(spec) == [] and forms.state_to_raw(spec, []) is None
    state = forms.value_to_state(spec, [item])
    assert state == [item] and state[0] is not item  # a copy: the form never edits the entry
    assert forms.state_to_raw(spec, state) == [item]
