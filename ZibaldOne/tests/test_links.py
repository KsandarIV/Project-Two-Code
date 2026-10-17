import pytest

from zibaldone.core.links import entry_names, is_person_template, name_key, outgoing_links, plain_text, wiki_targets
from zibaldone.core.packs import apply_install, find_builtin_pack, plan_install
from zibaldone.core.templates import BlockSpec, Entry, Template
from zibaldone.storage.database import Store


@pytest.fixture(params=[True, False], ids=["fts5", "like"])
def store(request, tmp_path):
    with Store.open(tmp_path, use_fts=request.param) as opened:
        for name in ("diario", "persone", "collezioni"):
            apply_install(plan_install(find_builtin_pack(name), opened), opened)
        yield opened


def person(store: Store, name: str, *nicknames: str, day: str = "2026-01-01") -> Entry:
    values = {"nome": name}
    if nicknames:
        values["soprannomi"] = list(nicknames)
    return store.add_entry("persona", values, day=day)


def test_wiki_targets_and_plain_text() -> None:
    text = "Con [[Marco]], [[marco]], [[Lucia Bianchi|Lucia]], [[Dune#Capitolo 2]], [[ ]], [[a\nb]] e [[]]"
    assert wiki_targets(text) == ["Marco", "Lucia Bianchi", "Dune"]
    assert plain_text("Con [[Marco]] e [[Lucia Bianchi|Lucia]]") == "Con Marco e Lucia"
    assert name_key("  MARCO   Rossi ") == "marco rossi"


def test_person_templates_and_names() -> None:
    pack = find_builtin_pack("persone")
    persona, incontro = (next(t for t in pack.templates if t.slug == slug) for slug in ("persona", "incontro"))
    assert is_person_template(persona) and not is_person_template(incontro)
    entry = Entry.new(persona, {"nome": "Marco Rossi", "soprannomi": ["Marco", "Marcolino"]})
    assert entry_names(entry, persona) == [("marco rossi", False), ("marco", True), ("marcolino", True)]
    own = Template("amico", "Amico", [BlockSpec("nome", "text", "Nome"), BlockSpec("alias", "tags", "Alias")], category="persone")
    assert is_person_template(own)
    assert entry_names(Entry.new(own, {"nome": "Ugo", "alias": ["U"]}), own) == [("ugo", False), ("u", True)]


def test_outgoing_links_from_blocks_and_texts() -> None:
    template = find_builtin_pack("persone").templates[0]
    incontro = next(t for t in find_builtin_pack("persone").templates if t.slug == "incontro")
    entry = Entry.new(incontro, {"titolo": "Cena", "con": ["a" * 32, "b" * 32], "cosa": "Con [[Marco]] e [[Lucia]]"})
    links = outgoing_links(entry, incontro)
    assert [(link.kind, link.target_ref, link.target_title) for link in links] == [
        ("block", "a" * 32, ""), ("block", "b" * 32, ""), ("wiki", None, "Marco"), ("wiki", None, "Lucia"),
    ]
    assert template.slug == "persona"


def test_block_links_and_backlinks(store) -> None:
    marco = person(store, "Marco Rossi")
    dinner = store.add_entry("incontro", {"titolo": "Cena", "con": [marco.id]}, day="2026-10-01")
    outgoing = store.outgoing(dinner.id)
    assert [(link.target, link.target_title, link.kind, link.block_label) for link in outgoing] == [(marco.id, "Marco Rossi", "block", "Con chi")]
    back = store.backlinks(marco.id)
    assert [(link.source, link.source_title, link.source_day, link.how) for link in back] == [(dinner.id, "Cena", "2026-10-01", "nel blocco «Con chi»")]


def test_wiki_links_resolve_ignoring_case_and_later(store) -> None:
    marco = person(store, "Marco")
    evening = store.add_entry("sera", {"fatto": "Visto [[MARCO]] e [[Lucia]]."}, day="2026-10-02")
    assert [(link.target, link.target_title) for link in store.outgoing(evening.id)] == [(marco.id, "Marco"), (None, "Lucia")]
    lucia = person(store, "lucia")
    assert store.outgoing(evening.id)[1].target == lucia.id
    renamed = person(store, "Giulia")
    store.update_entry(renamed.id, {"nome": "Lucia"})  # a second Lucia, created later: the first one stays
    assert store.outgoing(evening.id)[1].target == lucia.id
    store.update_entry(lucia.id, {"nome": "Lucia Verdi"})  # renamed away: [[Lucia]] moves to the other one
    assert store.outgoing(evening.id)[1].target == renamed.id
    assert [link.source for link in store.backlinks(renamed.id)] == [evening.id]


def test_people_and_nicknames_win_when_ambiguous(store) -> None:
    film = store.add_entry("film", {"titolo": "Marco"}, day="2026-01-01")
    note = store.add_entry("riflessione", {"titolo": "Su Marco", "testo": "Parlo di [[Marco]]"}, day="2026-10-01")
    assert store.outgoing(note.id)[0].target == film.id
    marco = person(store, "Marco Rossi", "Marco", day="2026-05-01")
    assert store.outgoing(note.id)[0].target == marco.id
    assert store.resolve_title("marco").id == marco.id
    assert store.resolve_title("nessuno") is None


def test_deleting_turns_incoming_links_unresolved(store) -> None:
    marco = person(store, "Marco Rossi", "Marco")
    other = person(store, "Marco")
    dinner = store.add_entry("incontro", {"titolo": "Cena", "con": [marco.id], "cosa": "Con [[Marco]] e [[Lucia]]"}, day="2026-10-01")
    assert [link.target for link in store.outgoing(dinner.id)] == [marco.id, other.id, None]  # a title beats a nickname
    store.delete_entry(other.id)
    assert store.outgoing(dinner.id)[1].target == marco.id  # [[Marco]] falls back to the nickname
    store.delete_entry(marco.id)
    after = store.outgoing(dinner.id)
    assert [(link.target, link.target_title, link.resolved) for link in after] == [
        (None, "Marco Rossi", False), (None, "Marco", False), (None, "Lucia", False),
    ]
    store.update_entry(dinner.id, {"dove": "Torino"})  # re-saving keeps the title of the deleted entry
    assert store.outgoing(dinner.id)[0].target_title == "Marco Rossi"
    again = person(store, "marco")
    assert store.outgoing(dinner.id)[1].target == again.id  # unresolved [[Marco]] resolves to a new Marco
    assert store.outgoing(dinner.id)[0].target is None  # an id in a link block never re-resolves by title
    store.delete_entry(dinner.id)
    assert store.backlinks(again.id) == []
    assert store.all_links() == []


def test_self_links_are_ignored(store) -> None:
    note = store.add_entry("riflessione", {"titolo": "Io", "testo": "Rileggo [[Io]]"}, day="2026-10-01")
    assert store.backlinks(note.id) == [] and store.outgoing(note.id) == []


def test_everything_about_a_person(store) -> None:
    marco = person(store, "Marco Rossi", "Marco")
    dinner = store.add_entry("incontro", {"titolo": "Cena", "con": [marco.id]}, day="2026-10-01")
    evening = store.add_entry("sera", {"fatto": "Telefonata con [[Marco]]"}, day="2026-10-03")
    mention = store.add_entry("riflessione", {"titolo": "Pensieri", "testo": "Oggi Marco mi ha fatto ridere"}, day="2026-10-04")
    store.add_entry("riflessione", {"titolo": "Altro", "testo": "Niente da dire"}, day="2026-10-05")
    about = store.about(marco.id)
    assert about.title == "Marco Rossi"
    assert [link.source for link in about.backlinks] == [evening.id, dinner.id]
    assert [hit.entry.id for hit in about.mentions] == [mention.id]


def test_encounters_are_found_by_the_linked_name(store) -> None:
    marco = person(store, "Marco Rossi")
    dinner = store.add_entry("incontro", {"titolo": "Cena", "con": [marco.id]}, day="2026-10-01")
    assert dinner.id in {hit.entry.id for hit in store.search("rossi").hits}
    store.update_entry(marco.id, {"nome": "Marcello Rossi"})
    assert dinner.id in {hit.entry.id for hit in store.search("marcello").hits}
    store.delete_entry(marco.id)
    assert dinner.id not in {hit.entry.id for hit in store.search("marcello").hits}


def test_tags_and_titles_helpers(store) -> None:
    first = store.add_entry("riflessione", {"testo": "…", "titolo": "A", "etichette": ["viaggi", "mare"]}, day="2026-10-01")
    store.add_entry("riflessione", {"testo": "…", "titolo": "B", "etichette": ["viaggi"]}, day="2026-10-02")
    assert store.list_tags() == [("viaggi", 2), ("mare", 1)]
    assert store.tags_by_entry()[first.id] == ["mare", "viaggi"]
    assert store.entry_titles()[first.id] == "A"
