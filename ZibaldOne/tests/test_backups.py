import hashlib
import io
import json
import sqlite3
import struct
import zipfile
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from zibaldone import __version__
from zibaldone.core import crypto
from zibaldone.core.crypto import ScryptParams
from zibaldone.core.templates import BlockSpec, Template
from zibaldone.storage import backups, keys
from zibaldone.storage.backups import (
    BackupError,
    BackupSettings,
    KeyRequiredError,
    RetentionPolicy,
    SnapshotInfo,
    create_snapshot,
    encrypt_existing_snapshots,
    find_snapshot,
    list_snapshots,
    load_backup_settings,
    maybe_auto_snapshot,
    maybe_pre_migration_snapshot,
    plan_retention,
    prune,
    restore_snapshot,
    save_backup_settings,
    verify_snapshot,
)
from zibaldone.storage.database import MIGRATIONS, Store, database_path
from zibaldone.storage.settings import load_settings, record_consent

UTC = timezone.utc
NOON = datetime(2026, 10, 17, 12, 0, tzinfo=UTC)
PASSPHRASE = "cavallo batteria graffetta"
LIBRO = Template("libro", "Libro", [BlockSpec("titolo", "text", "Titolo", required=True)])


@pytest.fixture(autouse=True)
def fast_scrypt(monkeypatch):
    monkeypatch.setattr(keys, "DEFAULT_SCRYPT_PARAMS", ScryptParams(n=2**10))


@pytest.fixture
def folder(tmp_path) -> Path:
    return tmp_path / "data"


def add_books(folder: Path, *titles: str) -> None:
    with Store.open(folder) as store:
        if store.find_template("libro") is None:
            store.save_template(LIBRO)
        for title in titles:
            store.add_entry("libro", {"titolo": title}, day="2026-10-01")


def book_titles(folder: Path) -> list:
    with Store.open(folder) as store:
        return sorted(entry.values["titolo"] for entry in store.list_entries())


def rewrite_zip(path: Path, **replace: bytes) -> None:
    with zipfile.ZipFile(path) as archive:
        members = {name: archive.read(name) for name in archive.namelist()}
    members.update(replace)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    path.write_bytes(buffer.getvalue())


def flip(path: Path, index: int) -> None:
    data = bytearray(path.read_bytes())
    data[index] ^= 0x01
    path.write_bytes(bytes(data))


# * — creating and reading —


def test_plain_snapshot_contents(folder) -> None:
    add_books(folder, "Dune", "Emma")
    record_consent(folder, accepted=True, notice_version=1)
    snapshot = create_snapshot(folder, "manual", "  prima   del trasloco ", now=NOON)
    assert snapshot.path.name == f"{snapshot.id}.zbsnap"
    assert snapshot.id.startswith("20261017T120000Z-") and len(snapshot.id) == 23
    assert snapshot.path.parent == folder / "backups"
    with zipfile.ZipFile(snapshot.path) as archive:
        assert sorted(archive.namelist()) == ["manifest.json", "settings.json", "zibaldone.db"]
        manifest = json.loads(archive.read("manifest.json"))
        database = archive.read("zibaldone.db")
    assert manifest["id"] == snapshot.id
    assert manifest["created_at"] == "2026-10-17T12:00:00+00:00"
    assert manifest["app_version"] == __version__
    assert manifest["schema_version"] == len(MIGRATIONS)
    assert manifest["reason"] == "manual" and manifest["note"] == "prima del trasloco"
    assert manifest["counts"] == {"entries": 2, "templates": 1}
    assert manifest["database"] == {"file": "zibaldone.db", "sha256": hashlib.sha256(database).hexdigest(), "size": len(database)}
    assert database.startswith(b"SQLite format 3\x00")
    assert not snapshot.encrypted


def test_no_database_no_snapshot(folder) -> None:
    with pytest.raises(BackupError, match="non ci sono ancora dati"):
        create_snapshot(folder)
    with pytest.raises(ValueError):
        create_snapshot(folder, "a caso")


def test_list_and_find(folder) -> None:
    add_books(folder, "Dune")
    older = create_snapshot(folder, now=NOON - timedelta(days=1))
    newer = create_snapshot(folder, "auto", now=NOON)
    listed = list_snapshots(folder)
    assert [item.id for item in listed] == [newer.id, older.id]
    assert listed[0].reason == "auto" and listed[0].entries == 1 and listed[0].reason_label == "automatica"
    assert find_snapshot(folder, newer.id).id == newer.id
    assert find_snapshot(folder, newer.id.split("-")[1]).id == newer.id
    assert find_snapshot(folder, "20261016").id == older.id
    with pytest.raises(BackupError, match="più istantanee"):
        find_snapshot(folder, "2026")
    with pytest.raises(BackupError, match="nessuna istantanea"):
        find_snapshot(folder, "19990101")


def test_unknown_files_in_backups_are_ignored(folder) -> None:
    add_books(folder, "Dune")
    create_snapshot(folder)
    (folder / "backups" / "appunti.txt").write_text("non mio")
    (folder / "backups" / "20261017T120000Z-zzzzzz.zbsnap").write_text("nome non valido")
    assert len(list_snapshots(folder)) == 1
    prune(folder, RetentionPolicy(0, 0, 0))
    assert (folder / "backups" / "appunti.txt").exists()


# * — verify —


def test_verify_good_snapshot(folder) -> None:
    add_books(folder, "Dune")
    snapshot = create_snapshot(folder)
    result = verify_snapshot(folder, snapshot.id)
    assert result.ok, result.problems
    assert not list(folder.glob(".zbtmp-*"))


def member_data(path: Path, name: str) -> tuple:
    """(offset, compressed size) of a zip member's data."""
    with zipfile.ZipFile(path) as archive:
        info = archive.getinfo(name)
    data = path.read_bytes()
    name_length, extra_length = struct.unpack("<HH", data[info.header_offset + 26 : info.header_offset + 30])
    return info.header_offset + 30 + name_length + extra_length, info.compress_size


def flip_changing(path: Path, member: str, index: int) -> None:
    """Flip a bit at `index` or at the first byte after it that really changes what the member unpacks to.

    A few bits of a deflate stream (padding, unused code lengths) change nothing, and which
    ones depends on the zlib build: a snapshot is only damaged if its content is.
    """
    with zipfile.ZipFile(path) as archive:
        before = archive.read(member)
    original = path.read_bytes()
    start, size = member_data(path, member)
    for at in range(index, start + size):
        flip(path, at)
        try:
            with zipfile.ZipFile(path) as archive:
                same = archive.read(member) == before
        except (zipfile.BadZipFile, zlib.error, EOFError):
            same = False
        if not same:
            return
        path.write_bytes(original)
    raise AssertionError("no byte of the member changes its content")


@pytest.mark.parametrize("member", ["manifest.json", "zibaldone.db"])
@pytest.mark.parametrize("where", ["start", "middle"])
def test_verify_detects_flipped_bytes(folder, member, where) -> None:
    add_books(folder, "Dune", "Emma", "Ivanhoe")
    snapshot = create_snapshot(folder)
    start, size = member_data(snapshot.path, member)
    # Not byte 0: its lowest bit is deflate's "last block" flag and flipping it leaves the content intact.
    flip_changing(snapshot.path, member, start + 1 if where == "start" else start + size // 2)
    assert not verify_snapshot(folder, snapshot.id).ok


def test_verify_detects_damaged_zip_directory(folder) -> None:
    add_books(folder, "Dune")
    snapshot = create_snapshot(folder)
    flip(snapshot.path, snapshot.path.stat().st_size - 10)  # end of central directory record
    assert not verify_snapshot(folder, snapshot.id).ok
    assert find_snapshot(folder, snapshot.id).problem


def test_verify_detects_wrong_hash_and_truncation(folder) -> None:
    add_books(folder, "Dune")
    snapshot = create_snapshot(folder)
    with zipfile.ZipFile(snapshot.path) as archive:
        database = archive.read("zibaldone.db")
    rewrite_zip(snapshot.path, **{"zibaldone.db": database[:-1] + b"\x01"})
    assert any("SHA-256" in problem for problem in verify_snapshot(folder, snapshot.id).problems)
    snapshot.path.write_bytes(snapshot.path.read_bytes()[:100])
    assert not verify_snapshot(folder, snapshot.id).ok


def newer_schema_snapshot(folder: Path) -> SnapshotInfo:
    folder.mkdir(parents=True)
    connection = sqlite3.connect(database_path(folder))
    connection.execute(f"PRAGMA user_version = {len(MIGRATIONS) + 1}")
    connection.close()
    return create_snapshot(folder)


def test_snapshot_from_newer_app_is_refused(folder) -> None:
    snapshot = newer_schema_snapshot(folder)
    assert any("più recente" in problem for problem in verify_snapshot(folder, snapshot.id).problems)
    with pytest.raises(BackupError, match="più recente"):
        restore_snapshot(folder, snapshot.id)


# * — restore —


def test_restore_and_undo(folder) -> None:
    add_books(folder, "Dune")
    first = create_snapshot(folder, now=NOON - timedelta(hours=1))
    add_books(folder, "Emma")
    result = restore_snapshot(folder, first.id)
    assert book_titles(folder) == ["Dune"]
    assert result.restored.id == first.id
    assert result.undo is not None and result.undo.reason == "pre-restore"
    undone = restore_snapshot(folder, result.undo.id)
    assert book_titles(folder) == ["Dune", "Emma"]
    assert undone.undo.reason == "pre-restore"
    assert not list(folder.glob(".zbtmp-*"))


def test_restore_keeps_device_settings(folder) -> None:
    add_books(folder, "Dune")
    record_consent(folder, accepted=True, notice_version=1)
    snapshot = create_snapshot(folder)
    save_backup_settings(folder, BackupSettings(auto=False, retention=RetentionPolicy(daily=3)))
    keys.setup_keys(folder, PASSPHRASE)
    keys_before = keys.keys_path(folder).read_bytes()
    settings_before = load_settings(folder)
    restore_snapshot(folder, snapshot.id)
    assert load_settings(folder) == settings_before
    assert load_backup_settings(folder).retention.daily == 3
    assert keys.keys_path(folder).read_bytes() == keys_before


def test_broken_snapshot_leaves_database_untouched(folder) -> None:
    add_books(folder, "Dune")
    snapshot = create_snapshot(folder)
    add_books(folder, "Emma")
    start, size = member_data(snapshot.path, "zibaldone.db")
    flip(snapshot.path, start + size // 2)
    count = len(list_snapshots(folder))
    with pytest.raises(BackupError, match="non è integra"):
        restore_snapshot(folder, snapshot.id)
    assert book_titles(folder) == ["Dune", "Emma"]
    assert len(list_snapshots(folder)) == count  # no pre-restore snapshot for a refused restore


def test_restore_refused_while_database_is_busy(folder) -> None:
    add_books(folder, "Dune")
    snapshot = create_snapshot(folder)
    busy = sqlite3.connect(database_path(folder))
    busy.execute("BEGIN IMMEDIATE")
    try:
        with pytest.raises(BackupError, match="in uso"):
            restore_snapshot(folder, snapshot.id)
    finally:
        busy.rollback()
        busy.close()
    assert len(list_snapshots(folder)) == 1


# * — retention —


def synthetic(days: int, end: datetime = NOON, per_day: int = 1) -> list:
    snapshots = []
    for back in range(days):
        for extra in range(per_day):
            moment = end - timedelta(days=back, hours=extra)
            snapshots.append(SnapshotInfo(id=f"{moment:%Y%m%dT%H%M%SZ}-000000", path=Path("x"), created_at=moment, size=1))
    return snapshots


def kept_days(plan) -> set:
    return {item.created_at.date().isoformat() for item in plan.keep}


def test_retention_daily_weekly_monthly() -> None:
    plan = plan_retention(synthetic(400), RetentionPolicy(daily=7, weekly=4, monthly=12), tz=UTC)
    daily = {f"2026-10-{day}" for day in range(11, 18)}
    weekly = {"2026-10-04", "2026-09-27"}  # Sundays ending the ISO weeks before; 10-17 and 10-11 already kept
    monthly = {
        "2026-09-30", "2026-08-31", "2026-07-31", "2026-06-30", "2026-05-31", "2026-04-30",
        "2026-03-31", "2026-02-28", "2026-01-31", "2025-12-31", "2025-11-30",
    }
    assert kept_days(plan) == daily | weekly | monthly
    assert len(plan.remove) == 400 - len(plan.keep)
    assert plan.why[plan.keep[0].id][0] == "la più recente"


def test_retention_keeps_only_newest_of_each_day_and_counts_days_with_snapshots() -> None:
    plan = plan_retention(synthetic(3, per_day=4), RetentionPolicy(daily=7, weekly=0, monthly=0), tz=UTC)
    assert len(plan.keep) == 3 and all(item.created_at.hour == 12 for item in plan.keep)
    sparse = [item for index, item in enumerate(synthetic(60)) if index % 10 == 0]
    plan = plan_retention(sparse, RetentionPolicy(daily=3, weekly=0, monthly=0), tz=UTC)
    assert kept_days(plan) == {"2026-10-17", "2026-10-07", "2026-09-27"}


def test_retention_always_keeps_latest_undo_and_protected() -> None:
    snapshots = synthetic(10)
    snapshots[5].reason = "pre-restore"
    snapshots[8].reason = "pre-restore"
    plan = plan_retention(snapshots, RetentionPolicy(0, 0, 0), protect=[snapshots[9].id], tz=UTC)
    assert {item.id for item in plan.keep} == {snapshots[0].id, snapshots[5].id, snapshots[9].id}
    assert "annulla l'ultimo ripristino" in plan.why[snapshots[5].id]


def test_prune_deletes_files_and_dry_run_does_not(folder) -> None:
    add_books(folder, "Dune")
    created = [create_snapshot(folder, now=NOON - timedelta(days=back)) for back in range(5)]
    policy = RetentionPolicy(daily=2, weekly=0, monthly=0)
    preview = prune(folder, policy, dry_run=True)
    assert preview.dry_run and len(preview.remove) == 3
    assert len(list_snapshots(folder)) == 5
    done = prune(folder, policy)
    assert [item.id for item in list_snapshots(folder)] == [created[0].id, created[1].id]
    assert not done.failed


def test_pre_restore_snapshot_survives_prune(folder) -> None:
    add_books(folder, "Dune")
    first = create_snapshot(folder, now=NOON - timedelta(days=1))
    undo = restore_snapshot(folder, first.id).undo
    create_snapshot(folder)  # same day as the undo point, and newer
    prune(folder, RetentionPolicy(daily=1, weekly=0, monthly=0))
    assert undo.id in {item.id for item in list_snapshots(folder)}


# * — automatic snapshots —


def test_auto_snapshot_interval(folder) -> None:
    assert maybe_auto_snapshot(folder, now=NOON) is None  # no data yet
    add_books(folder, "Dune")
    first = maybe_auto_snapshot(folder, now=NOON)
    assert first is not None and first.reason == "auto"
    assert maybe_auto_snapshot(folder, now=NOON + timedelta(hours=23)) is None
    second = maybe_auto_snapshot(folder, now=NOON + timedelta(hours=24))
    assert second is not None
    save_backup_settings(folder, BackupSettings(auto_interval_hours=2))
    assert maybe_auto_snapshot(folder, now=NOON + timedelta(hours=25)) is None
    assert maybe_auto_snapshot(folder, now=NOON + timedelta(hours=26)) is not None
    save_backup_settings(folder, BackupSettings(auto=False))
    assert maybe_auto_snapshot(folder, now=NOON + timedelta(days=30)) is None


def test_auto_snapshot_ignores_snapshots_from_the_future(folder) -> None:
    add_books(folder, "Dune")
    create_snapshot(folder, now=NOON + timedelta(days=1000))
    assert maybe_auto_snapshot(folder, now=NOON) is not None
    assert maybe_auto_snapshot(folder, now=NOON + timedelta(hours=1)) is None


def test_auto_snapshot_prunes(folder) -> None:
    add_books(folder, "Dune")
    save_backup_settings(folder, BackupSettings(retention=RetentionPolicy(daily=2, weekly=0, monthly=0)))
    for back in range(5, 0, -1):
        maybe_auto_snapshot(folder, now=NOON - timedelta(days=back))
    assert len(list_snapshots(folder)) == 2


def test_backup_settings_round_trip_and_validation(folder) -> None:
    record_consent(folder, accepted=True, notice_version=1)
    assert load_backup_settings(folder) == BackupSettings()
    save_backup_settings(folder, BackupSettings(auto=False, auto_interval_hours=12, retention=RetentionPolicy(1, 2, 3)))
    saved = load_settings(folder)
    assert saved["backup"] == {"auto": False, "auto_interval_hours": 12, "keep_daily": 1, "keep_weekly": 2, "keep_monthly": 3}
    assert saved["privacy"]["accepted"] is True
    saved["backup"]["keep_daily"] = -1
    (folder / "settings.json").write_text(json.dumps(saved), encoding="utf-8")
    with pytest.raises(BackupError, match="keep_daily"):
        load_backup_settings(folder)


def test_pre_migration_snapshot(folder, monkeypatch) -> None:
    add_books(folder, "Dune")
    assert maybe_pre_migration_snapshot(folder) is None  # already up to date
    monkeypatch.setattr(backups, "MIGRATIONS", (*MIGRATIONS, "CREATE TABLE future (x);"))
    snapshot = maybe_pre_migration_snapshot(folder)
    assert snapshot is not None and snapshot.reason == "pre-migration"


# * — encrypted snapshots (v0.0.7) —


def test_encrypted_snapshot_round_trip(folder) -> None:
    add_books(folder, "Diario segreto di Alex")
    new_keys = keys.setup_keys(folder, PASSPHRASE)
    snapshot = create_snapshot(folder, "manual", "nota privata")
    data = snapshot.path.read_bytes()
    assert snapshot.encrypted and crypto.is_sealed(data)
    for clear in (b"manifest.json", b"zibaldone.db", b"nota privata", b"Diario segreto", b"SQLite format"):
        assert clear not in data
    listed = list_snapshots(folder)[0]
    assert listed.encrypted and listed.reason == "manual" and listed.note is None and listed.entries is None
    detailed = list_snapshots(folder, new_keys.private_key)[0]
    assert detailed.note == "nota privata" and detailed.entries == 1
    with pytest.raises(KeyRequiredError):
        verify_snapshot(folder, snapshot.id)
    assert verify_snapshot(folder, snapshot.id, new_keys.private_key).ok
    add_books(folder, "Emma")
    private_key = keys.unlock_with_passphrase(folder, PASSPHRASE)
    with pytest.raises(KeyRequiredError):
        restore_snapshot(folder, snapshot.id)
    result = restore_snapshot(folder, snapshot.id, private_key)
    assert book_titles(folder) == ["Diario segreto di Alex"]
    assert result.undo.encrypted


def test_encrypted_snapshot_tampering_and_wrong_key(folder) -> None:
    add_books(folder, "Dune")
    keys.setup_keys(folder, PASSPHRASE)
    private_key = keys.unlock_with_passphrase(folder, PASSPHRASE)
    snapshot = create_snapshot(folder)
    other_key = crypto.generate_private_key()
    assert any("un'altra chiave" in problem for problem in verify_snapshot(folder, snapshot.id, other_key).problems)
    flip(snapshot.path, snapshot.path.stat().st_size - 40)
    problems = verify_snapshot(folder, snapshot.id, private_key).problems
    assert any("alterato" in problem for problem in problems)


def test_never_plain_once_encrypted_even_without_keys_file(folder) -> None:
    add_books(folder, "Dune")
    keys.setup_keys(folder, PASSPHRASE)
    create_snapshot(folder)
    keys.keys_path(folder).rename(folder / "keys.json.bak")
    with pytest.raises(BackupError, match="manca keys.json"):
        create_snapshot(folder)
    with pytest.raises(BackupError, match="manca keys.json"):
        maybe_auto_snapshot(folder, now=NOON + timedelta(days=3))
    assert all(crypto.is_sealed(path.read_bytes()) for path in (folder / "backups").iterdir())


def test_plain_snapshots_are_encrypted_after_setup(folder) -> None:
    add_books(folder, "Dune")
    first = create_snapshot(folder, "manual", "prima", now=NOON - timedelta(days=2))
    second = create_snapshot(folder, now=NOON - timedelta(days=1))
    broken = create_snapshot(folder, now=NOON)
    broken.path.write_bytes(broken.path.read_bytes()[:200])
    new_keys = keys.setup_keys(folder, PASSPHRASE)
    result = encrypt_existing_snapshots(folder, new_keys.private_key)
    assert result.encrypted == [first.id, second.id]
    assert [snapshot_id for snapshot_id, _ in result.failed] == [broken.id]
    for snapshot in (first, second):
        assert crypto.is_sealed(snapshot.path.read_bytes())
        assert verify_snapshot(folder, snapshot.id, new_keys.private_key).ok
    assert not crypto.is_sealed(broken.path.read_bytes())  # damaged: reported, never deleted
    assert list_snapshots(folder, new_keys.private_key)[-1].note == "prima"
    assert encrypt_existing_snapshots(folder, new_keys.private_key).encrypted == []
    with pytest.raises(BackupError, match="non corrisponde"):
        encrypt_existing_snapshots(folder, crypto.generate_private_key())


def test_single_snapshot_opens_with_recovery_code_on_a_new_device(folder, tmp_path) -> None:
    add_books(folder, "Dune")
    new_keys = keys.setup_keys(folder, PASSPHRASE)
    snapshot = create_snapshot(folder)
    device = tmp_path / "nuovo-dispositivo"
    (device / "backups").mkdir(parents=True)
    (device / "backups" / snapshot.path.name).write_bytes(snapshot.path.read_bytes())
    with pytest.raises(keys.WrongSecretError):
        backups.unlock_snapshot_with_recovery_code(device, snapshot.id, crypto.recovery_code_from_bytes(bytes(15)))
    private_key = backups.unlock_snapshot_with_recovery_code(device, snapshot.id, new_keys.recovery_code)
    result = restore_snapshot(device, snapshot.id, private_key)
    assert result.undo is None
    assert book_titles(device) == ["Dune"]
