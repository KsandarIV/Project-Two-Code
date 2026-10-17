import csv
import io
import zipfile

import pytest

from zibaldone.core.templates import BlockSpec, Template
from zibaldone.storage.database import Store
from zibaldone.storage.export import csv_files, export_csv, export_markdown, markdown_files, obsidian_tag, safe_file_name

LIBRO = Template(
    "libro",
    "Libro",
    [
        BlockSpec("titolo", "text", "Titolo", required=True),
        BlockSpec("voto", "rating", "Voto"),
        BlockSpec("generi", "tags", "Generi"),
        BlockSpec("note", "longtext", "Note"),
        BlockSpec("autore", "link", "Autore", options={"template": "persona"}),
    ],
)
PERSONA = Template("persona", "Persona", [BlockSpec("nome", "text", "Nome", required=True)])
SERA = Template("sera", "Sera", [BlockSpec("umore", "choice", "Umore", options={"choices": ["Bene", "Male"]})])
VUOTO = Template("vuoto", "Vuoto", [BlockSpec("x", "number", "X")])


@pytest.fixture
def store(tmp_path):
    with Store.open(tmp_path / "data") as opened:
        for template in (LIBRO, PERSONA, SERA, VUOTO):
            opened.save_template(template)
        yield opened


@pytest.fixture
def filled(store):
    herbert = store.add_entry("persona", {"nome": "Frank Herbert"}, day="2026-09-30")
    dune = store.add_entry(
        "libro",
        {"titolo": "Dune: parte 1/2", "voto": 4, "generi": ["fantascienza classica", "2026"], "note": "Riga uno\nRiga due", "autore": [herbert.id]},
        day="2026-10-01",
    )
    copy = store.add_entry("libro", {"titolo": "Dune: parte 1/2"}, day="2026-10-01")
    evenings = [store.add_entry("sera", {"umore": mood}, day="2026-10-02") for mood in ("Bene", "Male")]
    return {"herbert": herbert, "dune": dune, "copy": copy, "evenings": evenings}


def first_and_second(*entries):
    """Same day and same second: the export breaks the tie by id."""
    return sorted(entries, key=lambda entry: (entry.created_at, entry.id))


def test_file_names_are_safe_everywhere() -> None:
    assert safe_file_name('Dune: parte 1/2 "bis"?', "x") == "Dune parte 1 2 bis"
    assert safe_file_name("CON", "x") == "_CON"
    assert safe_file_name(" ... ", "riserva") == "riserva"
    assert safe_file_name("#tag [[link]] a^b|c", "x") == "tag link a b c"
    assert len(safe_file_name("a" * 300, "x")) == 80


def test_obsidian_tags() -> None:
    assert obsidian_tag("fantascienza classica") == "fantascienza-classica"
    assert obsidian_tag("2026") == "_2026"
    assert obsidian_tag("città, d'arte!") == "città-darte"


def test_markdown_layout_and_front_matter(store, filled) -> None:
    files = markdown_files(store)
    dune, herbert = filled["dune"], filled["herbert"]
    _, second_book = first_and_second(dune, filled["copy"])
    _, second_evening = first_and_second(*filled["evenings"])
    assert sorted(files) == sorted([
        "Libro/2026-10-01 Dune parte 1 2.md",
        f"Libro/2026-10-01 Dune parte 1 2 {second_book.short_id}.md",
        "Persona/2026-09-30 Frank Herbert.md",
        "Sera/2026-10-02 Sera.md",
        f"Sera/2026-10-02 Sera {second_evening.short_id}.md",
    ])
    assert markdown_files(store) == files  # same data, same names
    text = next(text for text in files.values() if dune.id in text)
    front, body = text.split("\n---\n", 1)
    assert front.splitlines() == [
        "---",
        "template: libro",
        "day: 2026-10-01",
        f'id: "{dune.id}"',
        'tags: ["fantascienza-classica", "_2026"]',
        f'created_at: "{dune.created_at}"',
        f'updated_at: "{dune.updated_at}"',
    ]
    assert "# Dune: parte 1/2\n" in body
    assert "## Voto\n\n★★★★☆\n" in body
    assert "## Generi\n\nfantascienza classica, 2026\n" in body
    assert "## Note\n\nRiga uno\nRiga due\n" in body
    assert "## Autore\n\n[[Persona/2026-09-30 Frank Herbert|Frank Herbert]]\n" in body
    assert f'id: "{herbert.id}"' in files["Persona/2026-09-30 Frank Herbert.md"]


def test_markdown_keeps_values_of_removed_blocks(store, filled) -> None:
    store.save_template(Template("libro", "Libro", [BlockSpec("titolo", "text", "Titolo", required=True)]), replace=True)
    text = next(text for text in markdown_files(store).values() if filled["dune"].id in text)
    assert "## voto\n\n4\n" in text
    assert '## generi\n\n["fantascienza classica", "2026"]\n' in text


def read_csv(text: str) -> list:
    return list(csv.reader(io.StringIO(text)))


def test_csv_columns_and_values(store, filled) -> None:
    files = csv_files(store)
    assert sorted(files) == ["libro.csv", "persona.csv", "sera.csv", "vuoto.csv"]
    header, *rows = read_csv(files["libro.csv"])
    assert header == ["id", "day", "created_at", "updated_at", "titolo", "voto", "generi", "note", "autore"]
    by_id = {row[0]: row for row in rows}
    dune = filled["dune"]
    assert by_id[dune.id] == [
        dune.id, "2026-10-01", dune.created_at, dune.updated_at, "Dune: parte 1/2", "4",
        '["fantascienza classica", "2026"]', "Riga uno\nRiga due", f'["{filled["herbert"].id}"]',
    ]
    assert by_id[filled["copy"].id][4:] == ["Dune: parte 1/2", "", "", "", ""]
    assert read_csv(files["vuoto.csv"]) == [["id", "day", "created_at", "updated_at", "x"]]


def test_csv_block_named_like_a_base_column(store) -> None:
    store.save_template(Template("evento", "Evento", [BlockSpec("day", "text", "Giorno a parole")]))
    store.add_entry("evento", {"day": "un martedì"}, day="2026-10-03")
    rows = read_csv(csv_files(store)["evento.csv"])
    assert rows[0][-1] == "blocco_day" and rows[1][1] == "2026-10-03" and rows[1][-1] == "un martedì"


def test_export_writes_zip_files(store, filled, tmp_path) -> None:
    markdown = export_markdown(store, tmp_path / "md.zip")
    assert (markdown.entries, markdown.templates) == (5, 3)
    with zipfile.ZipFile(tmp_path / "md.zip") as archive:
        assert sorted(archive.namelist()) == sorted(markdown_files(store))
        texts = [archive.read(name).decode("utf-8") for name in archive.namelist()]
    assert "★★★★☆" in next(text for text in texts if filled["dune"].id in text)
    table = export_csv(store, tmp_path / "csv.zip")
    assert (table.entries, table.templates) == (5, 4)
    with zipfile.ZipFile(tmp_path / "csv.zip") as archive:
        data = archive.read("libro.csv")
    assert data.startswith(b"\xef\xbb\xbf")  # BOM: Excel reads the accents
    with pytest.raises(ValueError, match="non esiste"):
        export_csv(store, tmp_path / "manca" / "csv.zip")
    assert not list(tmp_path.glob(".zbexport-*"))
