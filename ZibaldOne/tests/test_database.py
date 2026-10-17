import sqlite3

import pytest

from zibaldone.core.templates import BlockSpec, Template
from zibaldone.storage.database import MIGRATIONS, Store, StoreError


@pytest.fixture
def store(tmp_path):
    with Store.open(tmp_path) as opened:
        opened.save_template(
            Template(
                "libro",
                "Libro",
                [BlockSpec("titolo", "text", "Titolo", required=True), BlockSpec("voto", "rating", "Voto")],
            )
        )
        yield opened


def test_new_database_is_fully_migrated(tmp_path) -> None:
    with Store.open(tmp_path) as store:
        assert store.schema_version == len(MIGRATIONS)


def test_newer_database_is_refused(tmp_path) -> None:
    connection = sqlite3.connect(tmp_path / "zibaldone.db")
    connection.execute(f"PRAGMA user_version = {len(MIGRATIONS) + 1}")
    connection.close()
    with pytest.raises(StoreError, match="più recente"):
        Store.open(tmp_path)


def test_templates_crud(store) -> None:
    assert [template.slug for template in store.list_templates()] == ["libro"]
    with pytest.raises(StoreError):
        store.save_template(store.get_template("libro"))
    template = store.get_template("libro")
    template.name = "Libri"
    store.save_template(template, replace=True)
    assert store.get_template("libro").name == "Libri"
    assert store.free_slug("libro") == "libro_2"
    with pytest.raises(StoreError):
        store.get_template("film")


def test_entries_crud(store) -> None:
    first = store.add_entry("libro", {"titolo": "Dune", "voto": 5}, day="2026-10-01")
    second = store.add_entry("libro", {"titolo": "Emma"}, day="2026-10-05")
    assert [entry.id for entry in store.list_entries()] == [second.id, first.id]
    assert [entry.id for entry in store.list_entries(day_from="2026-10-02")] == [second.id]
    assert store.get_entry(first.id[:6]).values["titolo"] == "Dune"
    updated = store.update_entry(first.id, {"voto": None, "titolo": "Dune Messiah"})
    assert updated.values == {"titolo": "Dune Messiah"}
    assert store.get_entry(first.id).values == {"titolo": "Dune Messiah"}
    store.delete_entry(second.id)
    assert store.count_entries() == 1


def test_entry_reference_rules(store) -> None:
    store.add_entry("libro", {"titolo": "Dune"})
    with pytest.raises(StoreError, match="4 caratteri"):
        store.get_entry("ab")
    with pytest.raises(StoreError, match="nessuna voce"):
        store.get_entry("ffffffff")


def test_template_with_entries_cannot_be_deleted(store) -> None:
    store.add_entry("libro", {"titolo": "Dune"})
    with pytest.raises(StoreError, match="1 voci"):
        store.delete_template("libro")


def test_invalid_values_are_not_saved(store) -> None:
    with pytest.raises(ValueError):
        store.add_entry("libro", {"voto": 3})
    assert store.count_entries() == 0
