import pytest

from zibaldone.core.templates import BlockSpec, Entry, Template, slugify, validate_values


def book() -> Template:
    return Template(
        slug="libro",
        name="Libro",
        blocks=[
            BlockSpec("titolo", "text", "Titolo", required=True),
            BlockSpec("pagine", "number", "Pagine", options={"integer": True, "unit": "pagine"}),
            BlockSpec("voto", "rating", "Voto", options={"max": 5}),
            BlockSpec("generi", "tags", "Generi"),
        ],
    ).validate()


def test_slugify() -> None:
    assert slugify("Serie TV") == "serie_tv"
    assert slugify("Città è già") == "citta_e_gia"
    assert slugify("2025 letture") == "m_2025_letture"
    assert slugify("!!!") == "modello"


def test_template_round_trip_is_lossless() -> None:
    template = book()
    again = Template.from_dict(template.to_dict())
    assert again.to_dict() == template.to_dict()


def test_template_rules() -> None:
    with pytest.raises(ValueError):
        Template("Libro", "Libro", [BlockSpec("titolo", "text", "Titolo")]).validate()
    with pytest.raises(ValueError):
        Template("libro", "Libro", []).validate()
    with pytest.raises(ValueError):
        Template("libro", "Libro", [BlockSpec("a", "text", "A"), BlockSpec("a", "text", "B")]).validate()
    with pytest.raises(ValueError):
        Template("libro", "Libro", [BlockSpec("a", "text", "A")], title_block="b").validate()
    with pytest.raises(ValueError):
        Template("libro", "Libro", [BlockSpec("a", "text", "A")], color="rosso").validate()


def test_from_dict_rejects_unknown_fields() -> None:
    data = book().to_dict()
    data["script"] = "print('ciao')"
    with pytest.raises(ValueError):
        Template.from_dict(data)
    data = book().to_dict()
    data["blocks"][0]["eval"] = True
    with pytest.raises(ValueError):
        Template.from_dict(data)


def test_validate_values() -> None:
    template = book()
    values = validate_values(template, {"titolo": " Dune ", "voto": 5, "generi": [], "pagine": 412})
    assert values == {"titolo": "Dune", "voto": 5, "pagine": 412}
    with pytest.raises(ValueError, match="obbligatori"):
        validate_values(template, {"voto": 3})
    with pytest.raises(ValueError, match="non ha i blocchi"):
        validate_values(template, {"titolo": "Dune", "autore": "Herbert"})
    with pytest.raises(ValueError, match="Voto"):
        validate_values(template, {"titolo": "Dune", "voto": 9})


def test_entry_title_and_text() -> None:
    template = book()
    entry = Entry.new(template, {"titolo": "Dune", "voto": 4}, day="2026-10-17")
    assert entry.title(template) == "Dune"
    assert entry.day == "2026-10-17"
    assert len(entry.id) == 32
    assert entry.text_of(template) == {"Titolo": "Dune", "Voto": "★★★★☆"}
    untitled = Template("sera", "Sera", [BlockSpec("voto", "scale", "Voto")]).validate()
    assert Entry.new(untitled, {"voto": 7}, day="2026-10-17").title(untitled) == "Sera del 2026-10-17"


def test_a_template_in_several_areas() -> None:
    from zibaldone.core.templates import Template

    template = Template.from_dict({"slug": "x", "name": "X", "blocks": [{"key": "t", "type": "text", "label": "T"}], "area": "salute", "areas": ["svago", "salute", "svago"]})
    assert template.all_areas() == ["salute", "svago"]
    assert Template.from_dict(template.to_dict()).areas == ["svago"]
