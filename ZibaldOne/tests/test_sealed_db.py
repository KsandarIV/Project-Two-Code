import json
import threading

import pytest

from zibaldone.core import password
from zibaldone.core.crypto import ScryptParams
from zibaldone.core.templates import BlockSpec, Template
from zibaldone.storage import backups, database_key, keys, sealed_db
from zibaldone.storage.database import Store, database_exists, database_path
from zibaldone.storage.sealed_db import DatabaseLockedError

FAST_SCRYPT = ScryptParams(n=2**10)


@pytest.fixture(autouse=True)
def fast_scrypt(monkeypatch):
    monkeypatch.setattr(keys, "DEFAULT_SCRYPT_PARAMS", FAST_SCRYPT)


@pytest.fixture
def folder(tmp_path):
    folder = tmp_path / "data"
    folder.mkdir()
    return folder


def with_password(folder):
    made = password.generate()
    new = keys.create_keys(made, generated=True)
    keys.save_new_keys(folder, new)
    return made, new.recovery_code


def write_entry(folder, title="Ficciones"):
    with Store.open(folder) as store:
        if store.find_template("nota") is None:
            store.save_template(Template("nota", "Nota", [BlockSpec("testo", "text", "Testo")]))
        return store.add_entry("nota", {"testo": title}).id


def titles(folder):
    with Store.open(folder) as store:
        return sorted(entry.values["testo"] for entry in store.list_entries())


def test_nothing_changes_before_the_main_password(folder) -> None:
    write_entry(folder)
    assert database_key.seal_if_ready(folder) is None
    assert database_path(folder).exists() and not sealed_db.is_sealed(folder)
    keys.setup_keys(folder, "una passphrase scelta a mano")  # the terminal: not the main password yet
    assert database_key.seal_if_ready(folder) is None and not sealed_db.is_sealed(folder)


def test_the_plain_database_is_encrypted_and_nothing_is_readable_on_disk(folder) -> None:
    write_entry(folder, "segreto molto privato")
    with_password(folder)
    key = database_key.seal_if_ready(folder)
    assert key and sealed_db.is_sealed(folder) and not database_path(folder).exists() and database_exists(folder)
    on_disk = sealed_db.sealed_path(folder).read_bytes()
    assert b"segreto molto privato" not in on_disk and b"SQLite format" not in on_disk
    assert titles(folder) == ["segreto molto privato"]
    write_entry(folder, "secondo")
    sealed_db.forget(folder)  # a new start of the app
    with pytest.raises(DatabaseLockedError):
        Store.open(folder)
    assert database_key.unlock_with_stored_key(folder, database_key.stored_form(key))
    assert titles(folder) == ["secondo", "segreto molto privato"]


def test_a_new_database_is_encrypted_from_the_start(folder) -> None:
    with_password(folder)
    database_key.seal_if_ready(folder)
    assert sealed_db.is_sealed(folder) and not database_path(folder).exists()
    write_entry(folder)
    assert not database_path(folder).exists()


def test_the_password_or_the_code_bring_the_key_back(folder) -> None:
    write_entry(folder)
    made, code = with_password(folder)
    key = database_key.seal_if_ready(folder)
    assert "database_key" in json.loads(keys.keys_path(folder).read_text(encoding="utf-8"))
    sealed_db.forget(folder)
    with pytest.raises(keys.WrongSecretError):
        database_key.unlock_with_secret(folder, password="sbagliata davvero")
    assert database_key.unlock_with_secret(folder, password=made) == key
    sealed_db.forget(folder)
    assert database_key.unlock_with_secret(folder, recovery_code=code) == key
    assert titles(folder) == ["Ficciones"]
    assert not database_key.unlock_with_stored_key(folder, database_key.stored_form(b"x" * 32))
    assert not database_key.unlock_with_stored_key(folder, "non base64!")


def test_stores_in_many_threads_share_one_copy_and_lose_nothing(folder) -> None:
    with_password(folder)
    key = database_key.seal_if_ready(folder)
    write_entry(folder, "primo")
    threads = [threading.Thread(target=write_entry, args=(folder, f"voce {number}")) for number in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    sealed_db.forget(folder)  # what is on disk, read again
    sealed_db.unlock(folder, key)
    assert len(titles(folder)) == 9


def test_snapshots_and_restore_work_on_the_encrypted_database(folder) -> None:
    write_entry(folder, "prima")
    made, _ = with_password(folder)
    database_key.seal_if_ready(folder)
    snapshot = backups.create_snapshot(folder, "manual")
    write_entry(folder, "dopo")
    assert titles(folder) == ["dopo", "prima"]
    result = backups.restore_snapshot(folder, snapshot.id, keys.unlock_with_passphrase(folder, made))
    assert result.undo is not None
    assert titles(folder) == ["prima"] and not database_path(folder).exists()
    assert b"prima" not in sealed_db.sealed_path(folder).read_bytes()


# * — the terminal asks the main password —


def test_the_terminal_opens_the_encrypted_database_with_the_password(isolated_data_dir) -> None:
    from typer.testing import CliRunner

    from zibaldone.cli.app import app

    runner = CliRunner()
    assert runner.invoke(app, ["privacy", "accept"]).exit_code == 0
    write_entry(isolated_data_dir, "dal terminale")
    made, code = with_password(isolated_data_dir)
    database_key.seal_if_ready(isolated_data_dir)
    sealed_db.forget()  # a new command is a new process
    wrong = runner.invoke(app, ["entry", "list"], input="sbagliata davvero\n")
    assert wrong.exit_code == 1 and "password sbagliata" in wrong.output
    listed = runner.invoke(app, ["entry", "list"], input=f"{made}\n")
    assert listed.exit_code == 0 and "Il database è cifrato" in listed.output
    sealed_db.forget()
    with_code = runner.invoke(app, ["entry", "list"], input=f"\n{code}\n")
    assert with_code.exit_code == 0
    assert not database_path(isolated_data_dir).exists()
