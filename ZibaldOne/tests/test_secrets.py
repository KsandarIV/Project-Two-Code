"""Arcana (0.2.3): secret blocks sealed with the user's key, two levels, PIN, never in search or exports."""

from datetime import datetime, timedelta

import pytest
from typer.testing import CliRunner

from zibaldone.cli.app import app
from zibaldone.core import secrets as A
from zibaldone.core.crypto import ScryptParams
from zibaldone.core.packs import apply_install, find_builtin_pack, plan_install
from zibaldone.core.privacy import NOTICE_VERSION
from zibaldone.core.templates import Template
from zibaldone.storage import keys
from zibaldone.storage.database import Store, StoreError
from zibaldone.storage.export import entry_markdown, template_csv
from zibaldone.storage.paths import data_dir
from zibaldone.storage.settings import record_consent

PASSPHRASE = "cavallo batteria graffetta"
NOW = datetime(2026, 10, 17, 21, 0)
runner = CliRunner()


@pytest.fixture(autouse=True)
def fast_scrypt(monkeypatch):
    monkeypatch.setattr(keys, "DEFAULT_SCRYPT_PARAMS", ScryptParams(n=2**10))
    monkeypatch.setattr(keys, "PIN_SCRYPT_PARAMS", ScryptParams(n=2**10))


def install(store: Store, *names: str) -> None:
    for name in names:
        apply_install(plan_install(find_builtin_pack(name), store), store)


@pytest.fixture
def store(isolated_data_dir):
    with Store.open(isolated_data_dir) as opened:
        install(opened, "persone", "segreti")
        yield opened


def test_secrets_need_the_key_and_are_never_saved_in_clear(store: Store) -> None:
    with pytest.raises(StoreError, match="attiva prima la cifratura"):
        store.add_entry("diario_segreto", {"testo": "il mio segreto"})
    keys.setup_keys(store.path.parent, PASSPHRASE)
    entry = store.add_entry("diario_segreto", {"testo": "  il mio\nsegreto  "})
    raw = store.connection.execute("SELECT data FROM entries WHERE id = ?", (entry.id,)).fetchone()["data"]
    assert "segreto" not in raw and A.SECRET_PREFIX in raw
    assert A.value_level(entry.values["testo"]) == A.PROTECTED
    template = store.get_template("diario_segreto")
    assert entry.text_of(template) == {"Testo": A.LOCKED_TEXT}  # what search, exports and the anonymizer read
    assert store.search("segreto").total == 0
    with pytest.raises(ValueError, match="titolo"):
        Template.from_dict({"slug": "x", "name": "X", "title_block": "s", "blocks": [{"key": "s", "type": "secret", "label": "S"}]})


def test_two_levels_and_the_vault(store: Store) -> None:
    new_keys = keys.setup_keys(store.path.parent, PASSPHRASE)
    note = store.add_entry("note_mediche", {"tipo": "Visita", "dettagli": "allergia alla penicillina"})
    diary = store.add_entry("diario_segreto", {"testo": "caro diario"})
    assert A.value_level(note.values["dettagli"]) == A.MAXIMUM
    vault = A.Vault()
    assert not vault.is_open(NOW)
    with pytest.raises(A.SecretsError, match="chiusi"):
        vault.reveal(diary.values["testo"], NOW)
    vault.unlock([A.everyday_key(new_keys.private_key)], NOW)  # what the PIN opens
    assert vault.reveal(diary.values["testo"], NOW) == "caro diario"
    with pytest.raises(A.SecretsError, match="massimo"):
        vault.reveal(note.values["dettagli"], NOW)
    vault.unlock(keys.unlock_secrets_with_passphrase(store.path.parent, PASSPHRASE), NOW)
    assert vault.reveal(note.values["dettagli"], NOW) == "allergia alla penicillina"
    assert not vault.is_open(NOW + timedelta(minutes=A.VAULT_MINUTES + 1))  # closes by itself


def test_editing_keeps_untouched_secrets_and_seals_new_ones(store: Store) -> None:
    keys.setup_keys(store.path.parent, PASSPHRASE)
    anna = store.add_entry("persona", {"nome": "Anna", "indirizzo": "Via Roma 1", "documenti": "CI AB123"})
    changed = store.update_entry(anna.id, {"indirizzo": "Via Milano 2"})
    assert changed.values["documenti"] == anna.values["documenti"] and changed.values["indirizzo"] != anna.values["indirizzo"]
    vault = A.Vault()
    vault.unlock(keys.unlock_secrets_with_passphrase(store.path.parent, PASSPHRASE), NOW)
    assert vault.reveal(changed.values["indirizzo"], NOW) == "Via Milano 2"
    with pytest.raises(ValueError, match="rovinato"):
        store.update_entry(anna.id, {"documenti": A.SECRET_PREFIX + "bm9uIMOoIGNpZnJhdG8="})


def test_pin_opens_only_the_protected_level_and_gives_up_after_five(store: Store) -> None:
    folder = store.path.parent
    main = keys.setup_keys(folder, PASSPHRASE).private_key
    with pytest.raises(keys.KeysError, match="cifre"):
        keys.set_pin(folder, main, "12ab")
    keys.set_pin(folder, main, "246810")
    assert keys.has_pin(folder)
    assert A.key_id_of(keys.unlock_with_pin(folder, "246810")) == A.key_id_of(A.everyday_key(main))
    for left in (4, 3, 2, 1):
        with pytest.raises(keys.WrongSecretError, match=f"ancora {left}"):
            keys.unlock_with_pin(folder, "000000")
    with pytest.raises(keys.WrongSecretError, match="l'ho tolto"):
        keys.unlock_with_pin(folder, "000000")
    assert not keys.has_pin(folder)
    keys.change_passphrase(folder, PASSPHRASE, "una passphrase nuova di zecca")
    assert A.key_id_of(keys.unlock_secrets_with_passphrase(folder, "una passphrase nuova di zecca")[1]) == A.key_id_of(A.everyday_key(main))


def test_keys_set_up_before_0_2_3_learn_the_everyday_key_once(store: Store) -> None:
    folder = store.path.parent
    keys.setup_keys(folder, PASSPHRASE)
    document = keys._load(folder)
    document.pop(keys.SECRETS_FIELD)
    keys._save(folder, document)
    with pytest.raises(StoreError, match="una volta con la passphrase"):
        store.add_entry("diario_segreto", {"testo": "prima"})
    store.add_entry("note_mediche", {"dettagli": "il livello massimo usa la chiave dei backup"})
    keys.unlock_secrets_with_passphrase(folder, PASSPHRASE)
    assert A.value_level(store.add_entry("diario_segreto", {"testo": "dopo"}).values["testo"]) == A.PROTECTED


def test_exports_show_only_that_a_secret_exists(store: Store) -> None:
    keys.setup_keys(store.path.parent, PASSPHRASE)
    entry = store.add_entry("diario_segreto", {"testo": "non esportarmi"})
    template = store.get_template("diario_segreto")
    markdown = entry_markdown(entry, template, {})
    csv_text = template_csv(template, [entry])
    assert "non esportarmi" not in markdown + csv_text and A.LOCKED_TEXT in markdown and A.LOCKED_TEXT in csv_text


def test_people_pack_update_keeps_old_entries(isolated_data_dir) -> None:
    with Store.open(isolated_data_dir) as opened:
        old = find_builtin_pack("persone")
        persona = next(template for template in old.templates if template.slug == "persona")
        persona.blocks = [spec for spec in persona.blocks if spec.type != "secret"]
        old.version = "1.3.0"
        apply_install(plan_install(old, opened), opened)
        opened.add_entry("persona", {"nome": "Eva", "ruoli": ["sorella"]})
        plan = plan_install(find_builtin_pack("persone"), opened)
        assert {step.template.slug: step.action for step in plan.steps}["persona"] == "update"


def test_cli_pin_and_open(isolated_data_dir) -> None:
    record_consent(data_dir(), accepted=True, notice_version=NOTICE_VERSION)
    with Store.open(data_dir()) as opened:
        install(opened, "segreti")
    keys.setup_keys(data_dir(), PASSPHRASE)
    added = runner.invoke(app, ["entry", "add", "diario_segreto", "--set", "testo=solo per me"])
    assert added.exit_code == 0, added.output
    assert "solo per me" not in added.output
    with Store.open(data_dir()) as opened:
        entry_id = opened.list_entries()[0].id
    status = runner.invoke(app, ["segreti"])
    assert "Voci con segreti: 1" in status.output and "PIN: non scelto" in status.output, status.output
    chosen = runner.invoke(app, ["segreti", "pin"], input=f"{PASSPHRASE}\n135790\n135790\n")
    assert chosen.exit_code == 0 and "PIN scelto" in chosen.output, chosen.output
    shown = runner.invoke(app, ["entry", "show", entry_id[:8]])
    assert A.LOCKED_TEXT in shown.output and "solo per me" not in shown.output
    opened_entry = runner.invoke(app, ["segreti", "apri", entry_id[:8]], input="135790\n")
    assert opened_entry.exit_code == 0 and "solo per me" in opened_entry.output, opened_entry.output
    wrong = runner.invoke(app, ["segreti", "apri", entry_id[:8]], input="999999\n")
    assert wrong.exit_code == 1 and "ancora 4" in wrong.output
    assert "PIN tolto" in runner.invoke(app, ["segreti", "pin", "--togli"]).output
