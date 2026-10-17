"""Legami (0.2.2): typed relations, the family tree, the network and the strength of a bond."""

from datetime import date, timedelta

import pytest
from typer.testing import CliRunner

from zibaldone.cli.app import app
from zibaldone.core import people as P
from zibaldone.core import relations as L
from zibaldone.core.packs import apply_install, find_builtin_pack, plan_install
from zibaldone.core.privacy import NOTICE_VERSION
from zibaldone.storage.database import Store
from zibaldone.storage.paths import data_dir
from zibaldone.storage.settings import record_consent

TODAY = date(2026, 10, 17)
runner = CliRunner()


def day(offset: int) -> str:
    return (TODAY - timedelta(days=offset)).isoformat()


def install(store: Store, *names: str) -> None:
    for name in names:
        apply_install(plan_install(find_builtin_pack(name), store), store)


@pytest.fixture
def store(isolated_data_dir):
    with Store.open(isolated_data_dir) as opened:
        install(opened, "diario", "aree", "persone")
        yield opened


def family(store: Store) -> dict:
    """Grandpa Pietro → mum Anna (+ dad Paolo) → you and brother Luca; cousin Sara has no role in the tree."""
    pietro = store.add_entry("persona", {"nome": "Pietro", "ruoli": ["nonno"]})
    anna = store.add_entry("persona", {"nome": "Anna", "ruoli": ["madre"], "genitori": [pietro.id]})
    paolo = store.add_entry("persona", {"nome": "Paolo", "ruoli": ["padre"]})
    luca = store.add_entry("persona", {"nome": "Luca", "ruoli": ["fratello"], "genitori": [anna.id, paolo.id]})
    eva = store.add_entry("persona", {"nome": "Eva", "ruolo": "Famiglia", "genitori": [luca.id]})
    return {"pietro": pietro, "anna": anna, "paolo": paolo, "luca": luca, "eva": eva}


def test_links_read_both_ways(store: Store) -> None:
    ids = family(store)
    marco = store.add_entry("persona", {"nome": "Marco", "ruoli": ["collega"], "colleghi": [ids["luca"].id], "conosce": [ids["anna"].id]})
    ties = L.ties_of(P.load_people(store))
    assert [(tie.kind, tie.other) for tie in ties[ids["anna"].id]] == [
        ("genitore", ids["pietro"].id), ("figlio", ids["luca"].id), ("conosce", marco.id),
    ]
    assert [(tie.kind, tie.other) for tie in ties[ids["luca"].id]][-1] == ("collega", marco.id)
    assert ties[ids["pietro"].id] == [L.Tie(ids["anna"].id, "figlio")]


def test_family_tree_by_generation(store: Store) -> None:
    family(store)
    tree = L.family_tree(P.load_people(store))
    assert [(row.label, [member.name for member in row.members]) for row in tree] == [
        ("Nonni", ["Pietro"]),
        ("Genitori e zii", ["Anna", "Paolo"]),
        ("Tu, fratelli e cugini", ["Tu", "Luca"]),
        ("Figli e nipoti", ["Eva"]),
    ]
    you, luca = tree[2].members
    assert you.caption == "genitori: Anna e Paolo" and luca.caption == "fratello · genitori: Anna e Paolo"
    assert tree[1].members[0].caption == "madre · genitori: Pietro"


def test_tree_without_roles_and_with_odd_links(store: Store) -> None:
    """No role says where people stand from you: plain generations, and a loop of links does not hang."""
    a = store.add_entry("persona", {"nome": "Ada", "ruolo": "Famiglia"})
    b = store.add_entry("persona", {"nome": "Bea", "genitori": [a.id]})
    store.update_entry(a.id, {"genitori": [b.id, a.id]})  # a loop, and herself
    tree = L.family_tree(P.load_people(store))
    assert [row.label for row in tree] == ["Generazione 1", "Generazione 2"]
    assert "Tu" not in [member.name for row in tree for member in row.members]
    assert L.family_tree([]) == []


def test_network_in_common_and_graph(store: Store) -> None:
    lia = store.add_entry("persona", {"nome": "Lia", "ruoli": ["amica"]})
    nico = store.add_entry("persona", {"nome": "Nico", "ruoli": ["amico"], "conosce": [lia.id]})
    olga = store.add_entry("persona", {"nome": "Olga", "ruoli": ["collega"]})
    zoe = store.add_entry("persona", {"nome": "Zoe", "ruoli": ["amica"]})
    store.add_entry("incontro", {"titolo": "Cena", "con": [lia.id, nico.id, zoe.id]}, day=day(3))
    store.add_entry("incontro", {"titolo": "Cinema", "con": [lia.id, zoe.id]}, day=day(1))
    people = P.load_people(store)
    net = L.network(people)
    links = {link.person.name: link for link in net.connections(lia.id)}
    assert list(links) == ["Nico", "Zoe"] and links["Nico"].how == "si conoscono, 1 incontro insieme"
    assert links["Zoe"].how == "2 incontri insieme" and [person.name for person in links["Zoe"].in_common] == ["Nico"]
    assert links["Zoe"].common_line == "1 in comune" and net.connections(olga.id) == []
    graph = L.network_graph(net)
    assert {node.label for node in graph.nodes} == {"Lia", "Nico", "Olga", "Zoe"}
    assert graph.facts.edges == 3 and graph.facts.isolated == [(olga.id, "Olga")]
    assert all(0 <= node.x <= 1 and 0 <= node.y <= 1 for node in graph.nodes)
    social = L.network(people, area="sociale")
    assert [person.name for person in social.people] == ["Lia", "Nico", "Zoe"]


def test_strength_of_a_bond(store: Store) -> None:
    often = store.add_entry("persona", {"nome": "Spesso"})
    once = store.add_entry("persona", {"nome": "Raro"})
    store.add_entry("persona", {"nome": "Mai"})
    for offset in range(0, 70, 3):
        store.add_entry("incontro", {"titolo": "Caffè", "con": [often.id], "umore": "😄 Ottimo"}, day=day(offset))
    store.add_entry("incontro", {"titolo": "Auguri", "con": [once.id]}, day=day(300))
    people = {person.name: person for person in P.load_people(store)}
    assert L.strength(people["Spesso"], TODAY) == 10 and L.strength(people["Raro"], TODAY) == 0
    assert L.strength(people["Mai"], TODAY) is None and L.strength_line(people["Mai"], TODAY) == ""
    assert L.strength_line(people["Spesso"], TODAY) == "forza del legame 10/10 (molto stretto)"
    assert [person.name for person, _ in L.strongest(people.values(), TODAY)] == ["Spesso", "Raro"]
    assert [L.strength_word(score) for score in (9, 5, 3, 1)] == ["molto stretto", "stretto", "saltuario", "lontano"]


def test_add_tie_both_directions(store: Store) -> None:
    ids = family(store)
    people = P.load_people(store)
    anna, luca, eva = (P.find_person(people, name) for name in ("Anna", "Luca", "Eva"))
    assert L.add_tie(store, anna, L.PARENT, luca) is False  # already there
    with pytest.raises(P.PeopleError, match="già genitore"):
        L.add_tie(store, luca, L.CHILD, eva)  # Luca is Eva's parent, not her child
    with pytest.raises(P.PeopleError, match="sé stessa"):
        L.add_tie(store, anna, L.KNOWS, anna)
    assert L.add_tie(store, eva, L.KNOWS, anna) is True
    people = P.load_people(store)
    anna, eva = P.find_person(people, "Anna"), P.find_person(people, "Eva")
    assert L.add_tie(store, anna, L.KNOWS, eva) is False  # the same tie, written from the other side
    assert store.get_entry(ids["anna"].id).values["conosce"] == [ids["eva"].id]
    with pytest.raises(P.PeopleError, match="legame sconosciuto"):
        L.parse_tie("cugino")


def test_people_pack_update_keeps_old_entries(isolated_data_dir) -> None:
    """An entry written with Agorà 1.2.0 fits 1.3.0, so the update is not installed as a copy."""
    with Store.open(isolated_data_dir) as opened:
        old = find_builtin_pack("persone")
        persona = next(template for template in old.templates if template.slug == "persona")
        persona.blocks = [spec for spec in persona.blocks if spec.key not in L.BLOCK_OF.values()]
        old.version = "1.2.0"
        apply_install(plan_install(old, opened), opened)
        opened.add_entry("persona", {"nome": "Eva", "ruoli": ["sorella"], "frequenza": "Ogni mese"})
        plan = plan_install(find_builtin_pack("persone"), opened)
        assert {step.template.slug: step.action for step in plan.steps}["persona"] == "update"


def test_relatives_stay_out_of_everything_about_a_person(store: Store) -> None:
    """Relatives are in the Legami of the page, not among the entries that link the person."""
    family(store)
    page = P.person_page(store, P.find_person(P.load_people(store), "Anna"))
    assert page.groups == [] and page.total == 0


@pytest.fixture
def cli_data(isolated_data_dir):
    record_consent(data_dir(), accepted=True, notice_version=NOTICE_VERSION)
    with Store.open(data_dir()) as opened:
        install(opened, "diario", "persone")
        family(opened)
        opened.add_entry("persona", {"nome": "Marco", "ruoli": ["collega"]})
    return data_dir()


def invoke(*args: str):
    return runner.invoke(app, list(args))


def test_cli_tree_network_and_ties(cli_data) -> None:
    tree = invoke("persona", "albero")
    assert tree.exit_code == 0, tree.output
    assert tree.output.index("Nonni") < tree.output.index("Pietro") < tree.output.index("Genitori e zii") < tree.output.index("Tu · genitori: Anna e Paolo")
    tied = invoke("persona", "lega", "Marco", "collega", "Luca")
    assert tied.exit_code == 0 and "Legati: Marco è collega di Luca." in tied.output, tied.output
    assert "già" in invoke("persona", "lega", "Luca", "collega", "Marco").output
    assert invoke("persona", "lega", "Marco", "zio", "Luca").exit_code == 1
    shown = invoke("persona", "rete", "Luca")
    assert shown.exit_code == 0, shown.output
    assert "Anna · genitore" in shown.output and "Marco · collega" in shown.output and "Eva · figlio o figlia" in shown.output
    everyone = invoke("persona", "rete")
    assert everyone.exit_code == 0 and "Ancora nessun contatto" in everyone.output, everyone.output
    assert "Legami" in invoke("persona", "show", "Luca").output
