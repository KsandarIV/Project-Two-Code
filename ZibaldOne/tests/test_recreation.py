"""Svago avanzato (0.2.5): mezzi voti, preferiti, date che si scrivono da sole, import dai file di altri servizi."""

import csv
import gzip
import io
import json
from datetime import date, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from zibaldone.cli.app import app
from zibaldone.core import importers
from zibaldone.core.blocks import BLOCK_TYPES
from zibaldone.core.packs import apply_install, find_builtin_pack, plan_install
from zibaldone.core.privacy import NOTICE_VERSION
from zibaldone.core.templates import BlockSpec, Template, validate_values
from zibaldone.storage import database
from zibaldone.storage.database import Store
from zibaldone.storage.paths import data_dir
from zibaldone.storage.settings import record_consent

runner = CliRunner()


@pytest.fixture
def store(isolated_data_dir: Path):
    with Store.open(isolated_data_dir) as opened:
        apply_install(plan_install(find_builtin_pack("collezioni"), opened), opened)
        yield opened


def on_day(monkeypatch: pytest.MonkeyPatch, iso: str) -> None:
    """Make «today» in the Store a fixed day."""
    fixed = date.fromisoformat(iso)

    class Today(date):
        @classmethod
        def today(cls) -> date:
            return fixed

    monkeypatch.setattr(database, "date", Today)


def as_csv(header: list, *rows: list) -> bytes:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(header)
    writer.writerows(rows)
    return out.getvalue().encode("utf-8")


# * — the blocks —


def test_rating_in_half_points() -> None:
    rating = BLOCK_TYPES["rating"]
    half = {"max": 10, "half": True}
    assert rating.normalize(8.5, half) == 8.5 and rating.normalize(8, half) == 8 and isinstance(rating.normalize(8.0, half), int)
    with pytest.raises(ValueError, match="mezzi punti"):
        rating.normalize(8.3, half)
    with pytest.raises(ValueError, match="intero"):
        rating.normalize(3.5, {"max": 5})
    with pytest.raises(ValueError, match="da 0 a 10"):
        rating.normalize(10.5, half)
    assert rating.parse("8,5", half) == 8.5 and rating.parse("★★½", {"half": True}) == 2.5 and rating.parse("***", {}) == 3
    with pytest.raises(ValueError, match="non è un voto"):
        rating.parse("bello", {})
    assert rating.to_text(3.5, {"max": 5, "half": True}) == "★★★½☆" and rating.to_text(0.5, {"max": 5, "half": True}) == "½☆☆☆☆"
    assert rating.to_text(2, {"max": 5}) == "★★☆☆☆"
    assert rating.check_options({"max": 10, "half": True}) == half


def test_the_favorite_block_is_on_or_not_there() -> None:
    favorite = BLOCK_TYPES["favorite"]
    assert favorite.normalize(True, {}) is True and favorite.parse("sì", {}) is True and favorite.parse("No", {}) is False
    for wrong in ("sì", 1, None):
        with pytest.raises(ValueError):
            favorite.normalize(wrong, {})
    with pytest.raises(ValueError, match="sì o no"):
        favorite.parse("forse", {})
    assert favorite.is_empty(False) and favorite.is_empty(None) and not favorite.is_empty(True)
    template = Template.from_dict({"slug": "t", "name": "T", "blocks": [{"key": "p", "type": "favorite", "label": "P"}, {"key": "r", "type": "longtext", "label": "R", "options": {"spoiler": True}}]})
    assert validate_values(template, {"p": False, "r": "finale"}) == {"r": "finale"}


# * — start and finish dates —


def test_start_and_finish_dates_follow_the_status(store: Store, monkeypatch: pytest.MonkeyPatch) -> None:
    def stato(entry_id: str) -> dict:
        return store.get_entry(entry_id).values["stato"]

    on_day(monkeypatch, "2026-10-01")
    dune = store.add_entry("libro", {"titolo": "Dune", "stato": {"status": "ongoing", "current": 10, "total": 300}})
    assert stato(dune.id)["started"] == "2026-10-01" and "finished" not in stato(dune.id)
    on_day(monkeypatch, "2026-10-05")  # the form saves only status and counter: the dates stay
    store.update_entry(dune.id, {"stato": {"status": "ongoing", "current": 50, "total": 300}})
    assert stato(dune.id)["started"] == "2026-10-01"
    on_day(monkeypatch, "2026-10-09")
    store.update_entry(dune.id, {"stato": {"status": "completed", "total": 300}})
    assert (stato(dune.id)["started"], stato(dune.id)["finished"]) == ("2026-10-01", "2026-10-09")
    on_day(monkeypatch, "2026-10-12")  # read again: the finish date goes, the next one is new
    store.update_entry(dune.id, {"stato": {"status": "ongoing", "current": 5, "total": 300}})
    assert "finished" not in stato(dune.id)
    on_day(monkeypatch, "2026-10-15")
    store.update_entry(dune.id, {"stato": {"status": "completed", "total": 300}})
    assert (stato(dune.id)["started"], stato(dune.id)["finished"]) == ("2026-10-01", "2026-10-15")
    wish = store.add_entry("libro", {"titolo": "Ubik", "stato": {"status": "wishlist"}})
    assert set(stato(wish.id)) == {"status"}
    on_day(monkeypatch, "2026-10-20")
    store.update_entry(wish.id, {"stato": {"status": "ongoing"}})
    assert stato(wish.id)["started"] == "2026-10-20"
    old = store.add_entry("libro", {"titolo": "Walden", "stato": {"status": "completed"}}, stamp=False)  # an import knows better
    assert stato(old.id) == {"status": "completed"}
    store.update_entry(old.id, {"recensione": "bello", "stato": {"status": "completed"}})  # same status: no date made up
    assert stato(old.id) == {"status": "completed"}
    progress = BLOCK_TYPES["progress"]
    assert progress.normalize({"status": "completed", "started": "2024-01-02", "finished": "2024-02-03"}, {})["finished"] == "2024-02-03"
    with pytest.raises(ValueError):
        progress.normalize({"status": "completed", "started": "31/02/2024"}, {})


# * — import from other services' files —

GOODREADS = [
    "Book Id", "Title", "Author", "ISBN", "ISBN13", "My Rating", "Number of Pages", "Date Read", "Date Added", "Bookshelves", "Exclusive Shelf", "My Review", "Spoiler",
]
GOODREADS_ROWS = [
    ["1", "Le città invisibili", "Italo Calvino", '="8804391391"', '="9788804391395"', "5", "165", "2024/05/12", "2024/01/03", "fantascienza, favorites", "read", "Bellissimo<br/>davvero", ""],
    ["2", "Dune", "Frank Herbert", "", "", "0", "688", "", "2024/02/01", "", "to-read", "", ""],
    ["3", "Il nome della rosa", "Umberto Eco", "", "", "4", "512", "2024/06/20", "2024/01/01", "thriller", "read", "Il monaco è l'assassino", "true"],
    ["4", "", "Senza titolo", "", "", "0", "", "", "", "", "read", "", ""],
]


def test_goodreads_books_become_entries_with_dates_and_favorites(store: Store) -> None:
    parsed = importers.parse_goodreads(as_csv(GOODREADS, *GOODREADS_ROWS))
    assert [item.title for item in parsed.items] == ["Le città invisibili", "Dune", "Il nome della rosa"] and parsed.problems == ["riga 5: manca il titolo"]
    result = importers.import_items(store, parsed.items, dry_run=True)
    assert result.added == {"libro": 3} and store.count_entries("libro") == 0  # a dry run writes nothing
    result = importers.import_items(store, parsed.items)
    assert result.added == {"libro": 3} and result.summary() == "Aggiunti: 3 libri."
    city = next(entry for entry in store.list_entries(template="libro") if entry.values["titolo"] == "Le città invisibili")
    assert city.day == "2024-05-12" and city.values["autore"] == "Italo Calvino" and city.values["voto"] == 5
    assert city.values["stato"] == {"status": "completed", "current": 165, "total": 165, "finished": "2024-05-12"}  # no start date made up
    assert city.values["generi"] == ["fantascienza"] and city.values["preferito"] is True and city.values["isbn"] == "9788804391395"
    assert city.values["recensione"] == "Bellissimo\ndavvero"
    rose = next(entry for entry in store.list_entries(template="libro") if entry.values["titolo"] == "Il nome della rosa")
    assert "recensione_spoiler" in rose.values and "recensione" not in rose.values
    dune = next(entry for entry in store.list_entries(template="libro") if entry.values["titolo"] == "Dune")
    assert dune.values["stato"] == {"status": "wishlist", "total": 688} and "voto" not in dune.values
    again = importers.import_items(store, parsed.items)  # the same file twice adds nothing
    assert again.added == {} and again.existing == 3 and again.summary() == "Niente di nuovo da aggiungere. 3 già presenti, lasciati come sono."


def test_letterboxd_ratings_keep_half_stars_and_the_watchlist_is_a_wish_list(store: Store) -> None:
    header = ["Date", "Name", "Year", "Letterboxd URI", "Rating"]
    ratings = as_csv(header, ["2024-03-01", "Perfect Days", "2023", "https://boxd.it/a", "4.5"], ["2024-03-02", "Perfect Days", "2023", "https://boxd.it/a", "4.5"], ["2024-03-05", "Solaris", "1972", "https://boxd.it/b", "5"])
    parsed = importers.parse_letterboxd(ratings, "ratings.csv")
    assert [item.values["voto"] for item in parsed.items] == [4.5, 4.5, 5]
    result = importers.import_items(store, parsed.items)
    assert result.added == {"film": 2} and result.existing == 1
    perfect = next(entry for entry in store.list_entries(template="film") if entry.values["titolo"] == "Perfect Days")
    assert perfect.values["anno"] == 2023 and perfect.values["stato"]["status"] == "completed" and perfect.day == "2024-03-01"
    watchlist = importers.parse_letterboxd(as_csv(header[:4], ["2024-04-01", "Stalker", "1979", "https://boxd.it/c"]), "watchlist.csv")
    assert watchlist.items[0].values["stato"] == {"status": "wishlist"} and "voto" not in watchlist.items[0].values
    remake = importers.parse_letterboxd(as_csv(header[:4], ["2024-04-01", "Solaris", "2002", "https://boxd.it/d"]), "watched.csv")
    assert importers.import_items(store, remake.items).added == {"film": 1}  # same title, another year: another film


def test_myanimelist_xml_also_compressed_and_steam_json(store: Store) -> None:
    xml = """<?xml version="1.0" encoding="UTF-8" ?>
<myanimelist><myinfo><user_name>x</user_name></myinfo>
<anime><series_title><![CDATA[Cowboy Bebop]]></series_title><series_episodes>26</series_episodes><my_watched_episodes>26</my_watched_episodes>
<my_start_date>2024-01-02</my_start_date><my_finish_date>2024-02-03</my_finish_date><my_score>9</my_score><my_status>Completed</my_status><my_comments><![CDATA[Jazz]]></my_comments></anime>
<anime><series_title>Frieren</series_title><series_episodes>28</series_episodes><my_watched_episodes>5</my_watched_episodes>
<my_start_date>0000-00-00</my_start_date><my_finish_date>0000-00-00</my_finish_date><my_score>0</my_score><my_status>Watching</my_status></anime>
<anime><series_title>Akira</series_title><series_episodes>1</series_episodes><my_watched_episodes>0</my_watched_episodes><my_score>8</my_score><my_status>Plan to Watch</my_status></anime>
</myanimelist>""".encode("utf-8")
    parsed = importers.parse_myanimelist(gzip.compress(xml), "animelist.xml.gz")
    bebop, frieren, akira = parsed.items
    assert bebop.values["voto"] == 4.5 and bebop.values["recensione"] == "Jazz" and bebop.day == "2024-02-03"
    assert bebop.values["stato"] == {"status": "completed", "total": 26, "current": 26, "started": "2024-01-02", "finished": "2024-02-03"}
    assert frieren.values["stato"] == {"status": "ongoing", "total": 28, "current": 5} and "voto" not in frieren.values
    assert akira.values["stato"] == {"status": "wishlist", "total": 1} and akira.values["voto"] == 4
    assert importers.import_items(store, parsed.items).added == {"anime": 3}
    assert store.count_entries("anime") == 3
    games = {"response": {"game_count": 2, "games": [{"appid": 220, "name": "Half-Life 2", "playtime_forever": 1890, "rtime_last_played": 1700000000}, {"appid": 10, "name": "Counter-Strike", "playtime_forever": 0}]}}
    steam = importers.parse_steam(json.dumps(games).encode("utf-8"))
    half_life, strike = steam.items
    assert half_life.values["ore"] == 31.5 and half_life.values["piattaforma"] == "Steam" and half_life.day == datetime.fromtimestamp(1700000000).date().isoformat()
    assert strike.values["stato"] == {"status": "not_started"} and "ore" not in strike.values
    assert importers.import_items(store, steam.items).added == {"videogioco": 2}
    assert importers.parse_steam(json.dumps(games["response"]["games"]).encode("utf-8")).items[0].title == "Half-Life 2"  # the bare list works too


def test_wrong_files_are_refused_with_a_reason(store: Store) -> None:
    for parse, data, message in (
        (importers.parse_goodreads, as_csv(["Name", "Year"], ["Heat", "1995"]), "mancano le colonne Title"),
        (importers.parse_letterboxd, b"not,a,letterboxd\n1,2,3\n", "mancano le colonne Name, Year"),
        (importers.parse_myanimelist, b"<html></html>", "non è un file XML"),
        (importers.parse_myanimelist, b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><myanimelist/>', "struttura che non accetto"),
        (importers.parse_steam, b"not json", "non è un file JSON"),
        (importers.parse_steam, b'{"response": {"nothing": 1}}', "non è l'elenco dei giochi"),
        (importers.parse_goodreads, b"\x1f\x8bmarcio", "rovinato"),
    ):
        with pytest.raises(importers.ImportFileError, match=message):
            parse(data, "")
    assert importers.get_source("MAL").key == "myanimelist" and importers.get_source("Goodreads").name == "Goodreads"
    with pytest.raises(importers.ImportFileError, match="fonte sconosciuta"):
        importers.get_source("netflix")


def test_import_needs_the_museion_templates(isolated_data_dir: Path) -> None:
    with Store.open(isolated_data_dir) as empty:
        result = importers.import_items(empty, importers.parse_goodreads(as_csv(GOODREADS, GOODREADS_ROWS[0])).items)
    assert result.total == 0 and "manca il modello «Libro»" in result.problems[0]


def test_a_template_without_some_blocks_still_takes_the_import(isolated_data_dir: Path) -> None:
    with Store.open(isolated_data_dir) as bare:
        bare.save_template(Template(slug="libro", name="Libro", blocks=[BlockSpec("titolo", "text", "Titolo", required=True), BlockSpec("voto", "rating", "Voto")]))
        result = importers.import_items(bare, importers.parse_goodreads(as_csv(GOODREADS, GOODREADS_ROWS[0])).items)
        assert result.added == {"libro": 1} and bare.list_entries(template="libro")[0].values == {"titolo": "Le città invisibili", "voto": 5}


def test_cli_import_previews_then_adds(isolated_data_dir: Path, tmp_path: Path) -> None:
    record_consent(data_dir(), accepted=True, notice_version=NOTICE_VERSION)
    with Store.open(data_dir()) as opened:
        apply_install(plan_install(find_builtin_pack("collezioni"), opened), opened)
    export = tmp_path / "goodreads_library_export.csv"
    export.write_bytes(as_csv(GOODREADS, *GOODREADS_ROWS))
    preview = runner.invoke(app, ["importa", "goodreads", str(export), "--prova"])
    assert preview.exit_code == 0 and "Da aggiungere: 3 libri." in preview.output and "riga 5: manca il titolo" in preview.output, preview.output
    with Store.open(data_dir()) as opened:
        assert opened.count_entries("libro") == 0
    done = runner.invoke(app, ["importa", "goodreads", str(export)])
    assert done.exit_code == 0 and "Aggiunti: 3 libri." in done.output, done.output
    assert "già presenti" in runner.invoke(app, ["importa", "goodreads", str(export)]).output
    assert runner.invoke(app, ["importa", "netflix", str(export)]).exit_code == 1
    assert runner.invoke(app, ["importa", "steam", str(tmp_path / "manca.json")]).exit_code == 1
