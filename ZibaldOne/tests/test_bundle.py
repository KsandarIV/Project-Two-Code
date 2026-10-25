"""The backup file (`.zbbackup`, 0.3.1): export one snapshot, bring it back on another device."""

import json
import zipfile
from pathlib import Path

import pytest

from zibaldone.core.crypto import ScryptParams
from zibaldone.core.templates import BlockSpec, Template
from zibaldone.storage import backups, bundle, keys, media
from zibaldone.storage.backups import BackupError, KeyRequiredError, create_snapshot, list_snapshots
from zibaldone.storage.database import Store

PASSPHRASE = "cavallo batteria graffetta"
LIBRO = Template("libro", "Libro", [BlockSpec("titolo", "text", "Titolo", required=True)])


@pytest.fixture(autouse=True)
def fast_scrypt(monkeypatch):
    monkeypatch.setattr(keys, "DEFAULT_SCRYPT_PARAMS", ScryptParams(n=2**10))


@pytest.fixture
def folder(tmp_path) -> Path:
    return tmp_path / "phone"


@pytest.fixture
def device(tmp_path) -> Path:
    return tmp_path / "new-phone"


def titles(folder: Path) -> list:
    with Store.open(folder) as store:
        return sorted(entry.values["titolo"] for entry in store.list_entries(template="libro"))


def make_data(folder: Path, *names: str) -> None:
    with Store.open(folder) as store:
        if store.find_template("libro") is None:
            store.save_template(LIBRO)
        for name in names:
            store.add_entry("libro", {"titolo": name}, day="2026-10-01")


def rewrite(source: Path, target: Path, change) -> Path:
    """Copy a backup file member by member, letting `change(name, data)` alter or drop (None) each one."""
    with zipfile.ZipFile(source) as read, zipfile.ZipFile(target, "w", zipfile.ZIP_STORED) as write:
        for item in read.infolist():
            data = change(item.filename, read.read(item.filename))
            if data is not None:
                write.writestr(item.filename, data)
    return target


def test_export_names_the_file_after_the_snapshot_and_inspect_reads_it_without_opening_it(folder, tmp_path) -> None:
    make_data(folder, "Dune")
    snapshot = create_snapshot(folder)
    out = tmp_path / "Download"
    path = bundle.export_bundle(folder, snapshot.id, out)
    assert path.parent == out and path.name.startswith("zibaldone-") and path.suffix == ".zbbackup"
    info = bundle.inspect_bundle(path)
    assert info.ok and info.snapshot_id == snapshot.id and not info.encrypted and not info.has_keys and info.created_at == snapshot.created_at
    assert bundle.export_bundle(folder, snapshot.id, tmp_path / "mio.zbbackup").name == "mio.zbbackup"
    assert not list(out.glob(".zbtmp-*"))


def test_an_encrypted_backup_comes_back_on_a_new_device_with_the_passphrase_and_the_attachments(folder, device, tmp_path) -> None:
    make_data(folder, "Dune", "Solaris")
    attachment = media.add_bytes(folder, "foto.png", b"\x89PNG-pretend")
    new_keys = keys.setup_keys(folder, PASSPHRASE)
    with Store.open(folder) as store:
        store.add_entry("libro", {"titolo": "Con foto"}, day="2026-10-02")
    snapshot = create_snapshot(folder)
    path = bundle.export_bundle(folder, snapshot.id, tmp_path)
    info = bundle.inspect_bundle(path)
    assert info.ok and info.encrypted and info.has_keys and info.media == [attachment.file]
    result = bundle.restore_bundle(device, path, passphrase=PASSPHRASE)
    assert result.restored.id == snapshot.id and result.undo is None
    assert titles(device) == ["Con foto", "Dune", "Solaris"]
    assert keys.key_id(device) == new_keys.key_id  # the keys travelled in the file
    assert media.read(device, attachment.file) == b"\x89PNG-pretend"


def test_the_recovery_code_alone_opens_it_and_a_wrong_secret_changes_nothing(folder, device, tmp_path) -> None:
    make_data(folder, "Dune")
    new_keys = keys.setup_keys(folder, PASSPHRASE)
    path = bundle.export_bundle(folder, create_snapshot(folder).id, tmp_path)
    make_data(device, "Altro")
    before = titles(device)
    with pytest.raises(KeyRequiredError):
        bundle.restore_bundle(device, path)
    with pytest.raises(BackupError):
        bundle.restore_bundle(device, path, passphrase="sbagliata sbagliata sbagliata")
    assert titles(device) == before
    bundle.restore_bundle(device, path, recovery_code=new_keys.recovery_code)
    assert titles(device) == ["Dune"]
    assert any(item.reason == "pre-restore" for item in list_snapshots(device))  # the old data can be brought back


def test_a_device_with_other_keys_keeps_them_and_only_the_recovery_code_opens_the_file(folder, device, tmp_path) -> None:
    make_data(folder, "Dune")
    new_keys = keys.setup_keys(folder, PASSPHRASE)
    path = bundle.export_bundle(folder, create_snapshot(folder).id, tmp_path)
    make_data(device)
    mine = keys.setup_keys(device, "un'altra passphrase lunga")
    imported = bundle.import_bundle(device, path)
    assert imported.other_key and not imported.keys_installed and keys.key_id(device) == mine.key_id
    with pytest.raises(BackupError, match="codice di recupero"):
        bundle.restore_bundle(device, path, passphrase=PASSPHRASE)
    bundle.restore_bundle(device, path, recovery_code=new_keys.recovery_code)
    assert titles(device) == ["Dune"] and keys.key_id(device) == mine.key_id


def test_importing_twice_adds_nothing_and_a_plain_backup_needs_no_secret(folder, device, tmp_path) -> None:
    make_data(folder, "Dune")
    path = bundle.export_bundle(folder, create_snapshot(folder).id, tmp_path)
    first = bundle.import_bundle(device, path)
    again = bundle.import_bundle(device, path)
    assert first.snapshot.id == again.snapshot.id and len(list_snapshots(device)) == 1
    bundle.restore_bundle(device, path)
    assert titles(device) == ["Dune"]


@pytest.mark.parametrize(
    "damage, text",
    [
        (lambda name, data: None if name == "bundle.json" else data, "non è un backup"),
        (lambda name, data: b"{}" if name == "bundle.json" else data, "non è un backup"),
        (lambda name, data: json.dumps({**json.loads(data), "format_version": 99}).encode() if name == "bundle.json" else data, "formato diverso"),
        (lambda name, data: json.dumps({**json.loads(data), "schema_version": 999}).encode() if name == "bundle.json" else data, "più recente"),
        (lambda name, data: json.dumps({**json.loads(data), "snapshot": "../x.zbsnap"}).encode() if name == "bundle.json" else data, "manca l'istantanea"),
        (lambda name, data: None if name.endswith(".zbsnap") else data, "manca l'istantanea"),
    ],
)
def test_a_damaged_or_foreign_file_is_refused_with_a_message_and_changes_nothing(damage, text, folder, device, tmp_path) -> None:
    make_data(folder, "Dune")
    good = bundle.export_bundle(folder, create_snapshot(folder).id, tmp_path / "ok")
    bad = rewrite(good, tmp_path / "bad.zbbackup", damage)
    info = bundle.inspect_bundle(bad)
    assert not info.ok and text in " ".join(info.problems)
    with pytest.raises(BackupError, match=text):
        bundle.import_bundle(device, bad)
    assert not backups.backups_dir(device).exists() or not list_snapshots(device)


def test_files_that_are_not_backups_and_unexpected_members_are_refused(folder, device, tmp_path) -> None:
    make_data(folder, "Dune")
    good = bundle.export_bundle(folder, create_snapshot(folder).id, tmp_path / "ok")
    for name, content in (("a.zbbackup", b"non uno zip"), ("b.zbbackup", b"")):
        (tmp_path / name).write_bytes(content)
        assert not bundle.inspect_bundle(tmp_path / name).ok
    assert not bundle.inspect_bundle(tmp_path / "manca.zbbackup").ok
    extra = tmp_path / "extra.zbbackup"
    with zipfile.ZipFile(good) as read, zipfile.ZipFile(extra, "w", zipfile.ZIP_STORED) as write:
        for item in read.infolist():
            write.writestr(item.filename, read.read(item.filename))
        write.writestr("../fuori.txt", b"x")
    assert "non dovrebbero esserci" in " ".join(bundle.inspect_bundle(extra).problems)
    squeezed = tmp_path / "squeezed.zbbackup"
    with zipfile.ZipFile(good) as read, zipfile.ZipFile(squeezed, "w", zipfile.ZIP_DEFLATED) as write:
        for item in read.infolist():
            write.writestr(item.filename, read.read(item.filename))
    assert not bundle.inspect_bundle(squeezed).ok
    with pytest.raises(BackupError):
        bundle.import_bundle(device, extra)


def test_a_tampered_snapshot_inside_the_file_is_caught_by_the_restore(folder, device, tmp_path) -> None:
    make_data(folder, "Dune")
    keys.setup_keys(folder, PASSPHRASE)
    good = bundle.export_bundle(folder, create_snapshot(folder).id, tmp_path / "ok")
    bad = rewrite(good, tmp_path / "bad.zbbackup", lambda name, data: data[:-1] + bytes([data[-1] ^ 1]) if name.endswith(".zbsnap") else data)
    with pytest.raises(BackupError):
        bundle.restore_bundle(device, bad, passphrase=PASSPHRASE)
    assert not (device / "zibaldone.db").exists()


def test_a_new_installation_finds_the_newest_valid_backup_file_in_the_usual_folders(folder, device, tmp_path) -> None:
    home = tmp_path / "home"
    (home / "Downloads").mkdir(parents=True)
    (home / "Documents").mkdir()
    make_data(folder, "Dune")
    older = bundle.export_bundle(folder, create_snapshot(folder, now=backups._utc() - backups.timedelta(days=2)).id, home / "Documents")
    newer = bundle.export_bundle(folder, create_snapshot(folder).id, home / "Downloads")
    (home / "Downloads" / "rotto.zbbackup").write_bytes(b"niente")
    (home / "Downloads" / "appunti.txt").write_text("no")
    assert bundle.default_search_dirs() == [home / "Downloads", home / "Documents"]
    assert [item.path for item in bundle.find_backup_files()] == [newer, older]
    assert bundle.first_run_candidate(device).path == newer
    assert bundle.find_backup_files([tmp_path / "manca"]) == []


def test_nothing_is_offered_when_the_device_has_data_or_a_backup_of_its_own(folder, device, tmp_path) -> None:
    home = tmp_path / "home"
    home.joinpath("Downloads").mkdir(parents=True)
    make_data(folder, "Dune")
    bundle.export_bundle(folder, create_snapshot(folder).id, home / "Downloads")
    assert bundle.first_run_candidate(device) is not None
    make_data(device, "Mio")
    assert bundle.first_run_candidate(device) is None  # it has data
    (device / "zibaldone.db").unlink()
    assert bundle.first_run_candidate(device) is not None
    own = device / "backups"
    own.mkdir()
    (own / "20261017T120000Z-aaaaaa.zbsnap").write_bytes(b"x")
    assert bundle.first_run_candidate(device) is None  # it has a backup of its own
