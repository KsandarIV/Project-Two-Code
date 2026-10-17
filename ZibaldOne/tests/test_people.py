"""Agorà (0.2.1): people in more areas, roles, contacts, rhythm and "tutto di Marco"."""

from datetime import date, timedelta

import pytest
from typer.testing import CliRunner

from zibaldone.cli.app import app
from zibaldone.core import people as P
from zibaldone.core.blocks import BLOCK_TYPES
from zibaldone.core.packs import apply_install, find_builtin_pack, plan_install
from zibaldone.core.privacy import NOTICE_VERSION
from zibaldone.core.roles import role_area
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
        install(opened, "diario", "aree", "persone", "collezioni")
        yield opened


def test_bond_and_roles_put_a_person_in_areas(store: Store) -> None:
    assert (role_area("Madre"), role_area("capo"), role_area("Famiglia"), role_area("compagno di merende")) == ("famiglia", "lavoro", "famiglia", None)
    mum = store.add_entry("persona", {"nome": "Anna", "ruolo": "Famiglia", "ruoli": ["madre"]})
    boss = store.add_entry("persona", {"nome": "Bruno", "ruoli": ["capo", "compagno di merende", "medico"]})
    friend = store.add_entry("persona", {"nome": "Carla"})
    assert store.areas_of(mum.id) == ["famiglia"]
    assert store.areas_of(boss.id) == ["lavoro", "salute"]  # custom roles give no area
    assert store.areas_of(friend.id) == ["sociale"]  # the template's area is the fallback
    assert {entry.id for entry in store.list_entries(area="sociale")} == {friend.id}


def test_contacts_are_checked(store: Store) -> None:
    text = BLOCK_TYPES["text"]
    assert text.normalize(" +39 333  123 4567 ", {"format": "telefono"}) == "+39 333 123 4567"
    for value, kind in (("marco", "email"), ("12", "telefono"), ("chiamami", "telefono")):
        with pytest.raises(ValueError):
            text.normalize(value, {"format": kind})
    with pytest.raises(ValueError, match="Email"):
        store.add_entry("persona", {"nome": "Dario", "email": "dario-at-casa"})


def test_people_pack_update_keeps_old_entries(isolated_data_dir) -> None:
    """An entry written with Agorà 1.1.0 fits 1.2.0, so the update is not installed as a copy."""
    with Store.open(isolated_data_dir) as opened:
        old = find_builtin_pack("persone")
        persona = next(template for template in old.templates if template.slug == "persona")
        persona.blocks = [spec for spec in persona.blocks if spec.key not in ("ruoli", "telefono", "email", "social", "frequenza")]
        old.version = "1.1.0"
        apply_install(plan_install(old, opened), opened)
        opened.add_entry("persona", {"nome": "Eva", "ruolo": "Amico", "aree": ["svago"]})
        plan = plan_install(find_builtin_pack("persone"), opened)
        assert {step.template.slug: step.action for step in plan.steps}["persona"] == "update"


def test_contacts_last_contact_rhythm_and_due(store: Store) -> None:
    marco = store.add_entry("persona", {"nome": "Marco", "soprannomi": ["Marchino"], "frequenza": "Ogni settimana", "ruoli": ["amico"]})
    lia = store.add_entry("persona", {"nome": "Lia", "frequenza": "Ogni mese"})
    store.add_entry("persona", {"nome": "Nico"})
    for offset, kind in ((20, "Uscita"), (13, "Chiamata"), (10, "")):
        store.add_entry("incontro", {"titolo": "Insieme", "con": [marco.id], **({"tipo": kind} if kind else {})}, day=day(offset))
    store.add_entry("incontro", {"titolo": "Caffè", "con": [lia.id, marco.id], "tipo": "Di persona"}, day=day(2))
    people = P.load_people(store)
    assert [person.name for person in people] == ["Lia", "Marco", "Nico"]
    found = P.find_person(people, "marchino")
    assert found.id == marco.id and P.find_person(people, marco.id[:6]).id == marco.id and P.find_person(people, "ni").name == "Nico"
    assert [contact.label for contact in found.contacts] == ["Di persona", "Incontro", "Chiamata", "Uscita"]
    assert found.last_contact == TODAY - timedelta(days=2) and found.rhythm == 6.0
    assert found.contact_line(TODAY) == "sentiti 2 giorni fa (di persona)"
    assert not found.is_due(TODAY) and found.is_due(TODAY + timedelta(days=5))
    assert [person.name for person in P.due_people(people, TODAY + timedelta(days=40))] == ["Marco", "Lia"]
    assert "di solito vi sentite ogni 6 giorni" in found.rhythm_line(TODAY)
    assert (P.ago(None), P.ago(0), P.ago(1), P.ago(20), P.ago(100)) == ("mai", "oggi", "ieri", "2 settimane fa", "3 mesi fa")


def test_log_contact_and_everything_about_a_person(store: Store) -> None:
    mum = store.add_entry("persona", {"nome": "Anna", "ruoli": ["madre"]})
    store.add_entry("libro", {"titolo": "Lessico famigliare", "recensione": "regalo di [[Anna]]"})
    store.add_entry("riflessione", {"titolo": "Domenica", "testo": "Pranzo da Anna, senza collegamento"})
    person = P.find_person(P.load_people(store), "Anna")
    call = P.log_contact(store, person, "chiamata", "le ho detto del lavoro", day=day(1))
    assert call.values["titolo"] == "Chiamata con Anna" and call.values["tipo"] == "Chiamata"
    assert store.areas_of(call.id) == ["famiglia"]  # the contact goes in the person's area
    page = P.person_page(store, P.find_person(P.load_people(store), "Anna"))
    assert [(group.label, [item.title for item in group.items]) for group in page.groups] == [
        ("Famiglia", ["Chiamata con Anna"]), ("Svago", ["Lessico famigliare"]),
    ]
    assert [hit.title for hit in page.mentions] == ["Domenica"] and page.total == 3
    with pytest.raises(ValueError, match="Come"):
        P.log_contact(store, person, "piccione viaggiatore")


@pytest.fixture
def cli_data(isolated_data_dir):
    record_consent(data_dir(), accepted=True, notice_version=NOTICE_VERSION)
    with Store.open(data_dir()) as opened:
        install(opened, "diario", "persone")
        opened.add_entry("persona", {"nome": "Marco", "ruoli": ["collega"], "telefono": "+39 333 1234567", "frequenza": "Ogni settimana"})
        opened.add_entry("persona", {"nome": "Giulia", "ruoli": ["sorella"]})
    return data_dir()


def invoke(*args: str):
    return runner.invoke(app, list(args))


def test_cli_people(cli_data) -> None:
    listed = invoke("persona")
    assert listed.exit_code == 0, listed.output
    assert listed.output.index("Da sentire") < listed.output.index("Marco (collega) · mai sentiti") < listed.output.index("Giulia")
    heard = invoke("persona", "sentito", "marco", "--tipo", "chiamata", "--nota", "progetto nuovo")
    assert heard.exit_code == 0 and "Segnato: Chiamata con Marco" in heard.output
    assert "Da sentire" not in invoke("persona", "list").output
    assert "Giulia (sorella)" in invoke("persona", "list", "--area", "famiglia").output
    shown = invoke("persona", "show", "Marco")
    assert shown.exit_code == 0, shown.output
    assert "Telefono: +39 333 1234567" in shown.output and "Chiamata" in shown.output and "\nLavoro\n" in shown.output
    assert invoke("persona", "show", "Zeno").exit_code == 1


def test_area_index_follows_new_rules_at_open(isolated_data_dir) -> None:
    """A 0.2.0 database indexed Anna (bond Famiglia) under Sociale: opening it with 0.2.1 fixes that."""
    with Store.open(isolated_data_dir) as opened:
        install(opened, "persone")
        anna = opened.add_entry("persona", {"nome": "Anna", "ruolo": "Famiglia"})
        with opened.transaction():
            opened.connection.execute("UPDATE entry_areas SET area = 'sociale' WHERE entry_id = ?", (anna.id,))
            opened.connection.execute("UPDATE index_state SET value = '1' WHERE key = 'area_rules'")
    with Store.open(isolated_data_dir) as reopened:
        assert [entry.id for entry in reopened.list_entries(area="famiglia")] == [anna.id]
        assert reopened.list_entries(area="sociale") == []
