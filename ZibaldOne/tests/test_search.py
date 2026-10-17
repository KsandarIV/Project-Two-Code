import json
import sqlite3

import pytest

from zibaldone.core.packs import apply_install, find_builtin_pack, plan_install
from zibaldone.core.search import Query, Term, make_snippet, parse_query, words
from zibaldone.core.templates import Template
from zibaldone.storage.database import MIGRATIONS, Store, StoreError, fts5_available

HAS_FTS5 = fts5_available(sqlite3.connect(":memory:"))
ENGINES = ["fts5", "like"]


def install(store: Store, *packs: str) -> None:
    for name in packs:
        apply_install(plan_install(find_builtin_pack(name), store), store)


@pytest.fixture(params=ENGINES)
def store(request, tmp_path):
    if request.param == "fts5" and not HAS_FTS5:
        pytest.skip("SQLite senza FTS5")
    with Store.open(tmp_path, use_fts=request.param == "fts5") as opened:
        assert opened.search_engine == request.param
        install(opened, "diario", "persone")
        yield opened


def ids(result) -> set:
    return {hit.entry.id for hit in result.hits}


# — query parsing —


def test_parse_query_words_phrases_prefixes_exclusions() -> None:
    query = parse_query('Perché "frase  Esatta" parol* -escluso -"due parole" l\'amico')
    assert [str(term) for term in query.terms] == ["perche", '"frase esatta"', "parol*", "-escluso", '-"due parole"', '"l amico"']
    assert [term.exclude for term in query.terms] == [False, False, False, True, True, False]
    assert query.include[2].prefix and query.include[2].fts() == '"parol"*'
    assert query.fts_match() == '"perche" "frase esatta" "parol"* "l amico"'
    assert query.fts_exclusion() == '"escluso" OR "due parole"'
    assert query.include[0].like() == "% perche %" and query.include[2].like() == "% parol%"


def test_parse_query_never_fails_on_odd_input() -> None:
    assert parse_query('"non chiusa').terms == (Term(("non", "chiusa")),)
    assert parse_query("").blank and not parse_query("").unusable
    assert parse_query("🙂 *** -- \"\" ^ {}").unusable
    assert parse_query("marco marco").terms == (Term(("marco",)),)
    assert len(parse_query(" ".join(f"w{number}" for number in range(100))).terms) == 32
    for term in parse_query('a" OR b NEAR(c d) col:x ^e {f} \'; DROP TABLE entries; --').terms:
        assert all(word.isalnum() for word in term.words)


def test_words_fold_case_and_accents() -> None:
    assert words("Perché PERCHÉ città_vecchia Ñandú") == ["perche", "perche", "citta", "vecchia", "nandu"]


def test_snippet_highlights_best_window() -> None:
    text = " ".join(["riempitivo"] * 40) + " oggi Marco e io abbiamo parlato di libri " + " ".join(["altro"] * 40)
    snippet = make_snippet(text, parse_query("marco libr*"))
    assert snippet.text.startswith("…") and snippet.text.endswith("…")
    assert "[Marco]" in snippet.marked() and "[libri]" in snippet.marked()
    phrase = make_snippet("Abbiamo detto: frase esatta, poi altro.", parse_query('"frase esatta"'))
    assert phrase.marked("<", ">") == "Abbiamo detto: <frase esatta>, poi altro."
    assert make_snippet("", parse_query("x")).text == ""


# — searching —


def test_accents_and_case_are_ignored(store) -> None:
    entry = store.add_entry("riflessione", {"titolo": "Domande", "testo": "Perché scrivo? Per capire la città."}, day="2026-10-01")
    for query in ("perche", "PERCHÉ", "citta", "Città"):
        result = store.search(query)
        assert ids(result) == {entry.id}, query
        assert result.engine == store.search_engine
        assert result.fts == (store.search_engine == "fts5")
    assert "[Perché]" in store.search("perche").hits[0].snippet.marked()


def test_words_and_phrases_prefixes_exclusions(store) -> None:
    first = store.add_entry("riflessione", {"titolo": "Mare", "testo": "Una giornata al mare con gli amici di sempre."}, day="2026-10-01")
    second = store.add_entry("riflessione", {"titolo": "Montagna", "testo": "Gli amici sono partiti, io resto al lavoro."}, day="2026-10-02")
    third = store.add_entry("riflessione", {"titolo": "Lavoro", "testo": "Giornata di lavoro lunga."}, day="2026-10-03")
    assert ids(store.search("amici")) == {first.id, second.id}
    assert ids(store.search("amici mare")) == {first.id}
    assert ids(store.search('"amici di sempre"')) == {first.id}
    assert ids(store.search('"sempre amici"')) == set()
    assert ids(store.search("amic*")) == {first.id, second.id}
    assert ids(store.search("ami")) == set()
    assert ids(store.search("lavoro -amici")) == {third.id}
    assert ids(store.search('giornata -"al mare"')) == {third.id}
    assert ids(store.search("-lavoro")) == {first.id}
    assert ids(store.search("🙂")) == set() and store.search("🙂").query.unusable


def test_hostile_input_never_breaks_the_query(store) -> None:
    store.add_entry("riflessione", {"titolo": "Nota", "testo": "testo normale"}, day="2026-10-01")
    for raw in ['"', '***', 'NEAR(a b', 'title:nota', "'; DROP TABLE entries; --", "a AND OR NOT", "^nota", "{x} [y]",
                "nota\"testo", "-", "--nota", "a\\b", "%", "_", "50%_off", "\x00nota", "nota" * 300]:
        store.search(raw)
    assert store.count_entries() == 1
    assert store.search('nota" OR "x').total == 0  # OR is just a word: nota AND or AND x
    assert store.search('nota "testo').total == 1  # an unterminated quote runs to the end


def test_filters_template_tags_days_limit(store) -> None:
    a = store.add_entry("riflessione", {"testo": "…", "titolo": "Viaggio a Roma", "etichette": ["#Viaggi", "Famiglia"]}, day="2026-09-01")
    b = store.add_entry("riflessione", {"testo": "…", "titolo": "Viaggio a Napoli", "etichette": ["viaggi"]}, day="2026-10-01")
    c = store.add_entry("sera", {"fatto": "Programmato un viaggio"}, day="2026-10-05")
    assert ids(store.search("viaggi*")) == {a.id, b.id, c.id}
    assert ids(store.search("viaggi*", template="riflessione")) == {a.id, b.id}
    assert ids(store.search("viaggi*", tags=["VIAGGI"])) == {a.id, b.id}
    assert ids(store.search("viaggi*", tags=["#viaggi", "famiglia"])) == {a.id}
    assert ids(store.search("viaggi*", since="2026-09-15")) == {b.id, c.id}
    assert ids(store.search("viaggi*", until="01/10/2026")) == {a.id, b.id}
    limited = store.search("viaggi*", limit=2)
    assert len(limited.hits) == 2 and limited.total == 3
    listed = store.search("", tags=["viaggi"])
    assert [hit.entry.id for hit in listed.hits] == [b.id, a.id] and listed.total == 2
    with pytest.raises(ValueError):
        store.search("x", since="ieri l'altro")


def test_title_and_tags_rank_above_body(store) -> None:
    body = store.add_entry("riflessione", {"titolo": "Altro", "testo": "Parlo anche di Dune, a un certo punto, tra mille altre cose."}, day="2026-10-02")
    title = store.add_entry("riflessione", {"titolo": "Dune", "testo": "Un libro."}, day="2026-10-01")
    hits = store.search("dune").hits
    assert [hit.entry.id for hit in hits] == [title.id, body.id]
    assert hits[0].rank >= hits[1].rank
    assert hits[0].title_highlights == ((0, 4),)


def test_index_follows_updates_and_deletes(store) -> None:
    entry = store.add_entry("riflessione", {"titolo": "Bozza", "testo": "primo pensiero"}, day="2026-10-01")
    store.update_entry(entry.id, {"testo": "secondo pensiero"})
    assert ids(store.search("primo")) == set()
    assert ids(store.search("secondo")) == {entry.id}
    store.update_entry(entry.id, {}, day="2026-10-09")
    assert ids(store.search("secondo", since="2026-10-05")) == {entry.id}
    store.delete_entry(entry.id)
    assert ids(store.search("secondo")) == set()
    assert store.search("").total == 0


def test_index_write_failure_rolls_back_the_entry(store, monkeypatch) -> None:
    def broken(*args, **kwargs):
        raise RuntimeError("disco pieno")

    monkeypatch.setattr(store, "_write_document", broken)
    with pytest.raises(RuntimeError):
        store.add_entry("riflessione", {"testo": "…", "titolo": "Non salvata"}, day="2026-10-01")
    assert store.count_entries() == 0


def test_template_change_reindexes_titles(store) -> None:
    entry = store.add_entry("riflessione", {"titolo": "Titolo vecchio", "testo": "Corpo del testo"}, day="2026-10-01")
    template = store.get_template("riflessione")
    data = template.to_dict()
    data["title_block"] = "testo"
    store.save_template(Template.from_dict(data), replace=True)
    hit = store.search("corpo").hits[0]
    assert hit.title == "Corpo del testo" and hit.entry.id == entry.id


@pytest.mark.skipif(not HAS_FTS5, reason="SQLite senza FTS5")
def test_both_engines_agree(tmp_path) -> None:
    with Store.open(tmp_path) as store:
        install(store, "diario", "collezioni")
        texts = [
            ("riflessione", {"titolo": "Perché scrivere", "testo": "Scrivere per capire, perché la memoria inganna.", "etichette": ["scrittura"]}),
            ("riflessione", {"titolo": "Città", "testo": "La città di notte: luci, rumori, l'amico Paolo.", "etichette": ["notte"]}),
            ("sera", {"fatto": "Ho letto Dune e scritto due pagine.", "imparato": "La pazienza paga."}),
            ("libro", {"titolo": "Dune", "autore": "Frank Herbert", "generi": ["fantascienza"], "recensione": "Sabbia e potere."}),
            ("film", {"titolo": "Dune", "regista": "Villeneuve", "recensione": "Immagini potenti, sabbia ovunque."}),
        ]
        for number, (slug, values) in enumerate(texts, 1):
            store.add_entry(slug, values, day=f"2026-10-{number:02d}")
        for query in ["perche", "dune", "sabbia potere", '"sabbia e potere"', "pot*", "dune -film", "scriv*", "-dune",
                      "amico", '"l amico"', "fantascienza", "notte", "citta luci", "zzz", ""]:
            fts, like = store.search(query, engine="fts5"), store.search(query, engine="like")
            assert ids(fts) == ids(like), query
            assert fts.total == like.total, query
            assert (fts.engine, like.engine) == ("fts5", "like")


def test_forcing_fts_without_it_is_refused(tmp_path) -> None:
    with Store.open(tmp_path, use_fts=False) as store:
        assert store.search_engine == "like" and not store.search("x").fts
        with pytest.raises(StoreError, match="FTS5"):
            store.search("x", engine="fts5")


def test_environment_variable_disables_fts(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ZIBALDONE_NO_FTS", "1")
    with Store.open(tmp_path) as store:
        assert store.search_engine == "like"


# — migration and self-repair —


def make_v1_database(folder) -> dict:
    """A database as written by ZibaldOne before 0.1.2 (schema 1, no indexes)."""
    pack = find_builtin_pack("persone")
    connection = sqlite3.connect(folder / "zibaldone.db")
    connection.executescript(MIGRATIONS[0] + "; PRAGMA user_version = 1;")
    for template in pack.templates:
        connection.execute("INSERT INTO templates VALUES (?, ?, 't', 't')", (template.slug, json.dumps(template.to_dict())))
    marco = "a" * 32
    meeting = "b" * 32
    rows = [
        (marco, "persona", "2026-01-01", {"nome": "Marco", "note": "Amico dell'università, ama il caffè"}),
        (meeting, "incontro", "2026-02-01", {"titolo": "Caffè in centro", "con": [marco], "cosa": "Con [[marco]] e [[Giulia]]"}),
    ]
    for entry_id, slug, day, values in rows:
        connection.execute("INSERT INTO entries VALUES (?, ?, ?, ?, ?, ?)", (entry_id, slug, day, json.dumps(values), day, day))
    connection.commit()
    connection.close()
    return {"marco": marco, "meeting": meeting}


@pytest.mark.parametrize("use_fts", [True, False])
def test_migration_backfills_search_and_links(tmp_path, use_fts) -> None:
    if use_fts and not HAS_FTS5:
        pytest.skip("SQLite senza FTS5")
    made = make_v1_database(tmp_path)
    with Store.open(tmp_path, use_fts=use_fts) as store:
        assert store.schema_version == len(MIGRATIONS) >= 2
        assert ids(store.search("universita")) == {made["marco"]}
        assert ids(store.search("caffe")) == {made["marco"], made["meeting"]}
        back = store.backlinks(made["marco"])
        assert {(link.source, link.kind) for link in back} == {(made["meeting"], "block"), (made["meeting"], "wiki")}
        outgoing = store.outgoing(made["meeting"])
        assert [(link.target_title, link.resolved) for link in outgoing] == [("Marco", True), ("Marco", True), ("Giulia", False)]


@pytest.mark.skipif(not HAS_FTS5, reason="SQLite senza FTS5")
def test_writes_without_fts_are_caught_up_where_fts_exists(tmp_path) -> None:
    with Store.open(tmp_path) as store:
        install(store, "diario")
        store.add_entry("sera", {"fatto": "scritto sul computer"}, day="2026-10-01")
    with Store.open(tmp_path, use_fts=False) as phone:
        phone_entry = phone.add_entry("sera", {"fatto": "scritto sul telefono"}, day="2026-10-02")
        phone.delete_entry(phone.search("computer").hits[0].entry.id)
    with Store.open(tmp_path) as store:
        assert store.search_engine == "fts5"
        assert ids(store.search("telefono")) == {phone_entry.id}
        assert ids(store.search("computer")) == set()


def test_entries_changed_outside_the_store_are_reindexed(tmp_path) -> None:
    with Store.open(tmp_path) as store:
        install(store, "diario")
        entry = store.add_entry("riflessione", {"testo": "…", "titolo": "Prima"}, day="2026-10-01")
    connection = sqlite3.connect(tmp_path / "zibaldone.db")
    connection.execute("UPDATE entries SET data = ?, updated_at = 'dopo' WHERE id = ?", (json.dumps({"titolo": "Seconda"}), entry.id))
    connection.commit()
    connection.close()
    with Store.open(tmp_path) as store:
        assert ids(store.search("seconda")) == {entry.id}
        assert ids(store.search("prima")) == set()


def test_rebuild_indexes_is_idempotent(store) -> None:
    entry = store.add_entry("riflessione", {"titolo": "Idem", "testo": "uguale"}, day="2026-10-01")
    store.rebuild_indexes()
    store.rebuild_indexes()
    assert ids(store.search("uguale")) == {entry.id}
    assert store.search("").total == 1


def test_query_object_is_accepted(store) -> None:
    entry = store.add_entry("riflessione", {"testo": "…", "titolo": "Oggetto"}, day="2026-10-01")
    assert ids(store.search(Query("oggetto", (Term(("oggetto",)),)))) == {entry.id}
