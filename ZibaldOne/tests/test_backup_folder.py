"""The visible folder of backup files (0.3.3): subfolders by kind, rotation, the user's files set aside."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from zibaldone.core.crypto import ScryptParams
from zibaldone.core.templates import BlockSpec, Template
from zibaldone.storage import backup_folder as bf
from zibaldone.storage import backups, bundle, keys
from zibaldone.storage.database import Store

LIBRO = Template("libro", "Libro", [BlockSpec("titolo", "text", "Titolo", required=True)])


@pytest.fixture
def data(tmp_path) -> Path:
    folder = tmp_path / "private"
    with Store.open(folder) as store:
        store.save_template(LIBRO)
        store.add_entry("libro", {"titolo": "Uno"})
    return folder


@pytest.fixture
def target(tmp_path) -> Path:
    return tmp_path / "ZibaldOne" / "Data"


def snap(data: Path, reason: str, day: int) -> None:
    backups.create_snapshot(data, reason, now=datetime(2026, 3, 1, 1, 0, tzinfo=timezone.utc) + timedelta(days=day))


def names(directory: Path) -> list:
    return sorted(path.name for path in directory.glob("*.zbbackup"))


def test_the_app_mode_puts_each_kind_in_its_subfolder_and_does_not_repeat(data, target) -> None:
    snap(data, "auto", 0)
    snap(data, "week", 1)
    snap(data, "manual", 2)
    assert len(bf.export_snapshots(data, target, bf.MODE_APP)) == 3
    assert len(names(bf.tier_dir(target, "auto"))) == len(names(bf.tier_dir(target, "week"))) == len(names(bf.tier_dir(target, "manual"))) == 1
    assert bf.export_snapshots(data, target, bf.MODE_APP) == []
    assert all(bundle.inspect_bundle(item.path).ok for item in bf.list_files(target))


def test_the_user_mode_writes_the_newest_flat(data, target) -> None:
    snap(data, "manual", 0)
    snap(data, "manual", 1)
    [written] = bf.export_snapshots(data, target, bf.MODE_USER)
    assert written.parent == target and [item.kind for item in bf.list_files(target)] == ["altri"]


def test_rotation_keeps_seven_daily_and_the_old_one_is_deleted_or_goes_to_history(data, target) -> None:
    for day in range(8):
        snap(data, "auto", day)
        bf.export_snapshots(data, target, bf.MODE_APP)
    daily = bf.tier_dir(target, "auto")
    oldest = names(daily)[0]
    assert len(names(daily)) == 8
    gone = bf.rotate(target)
    assert [path.name for path in gone] == [oldest] and len(names(daily)) == 7 and not (target / bf.HISTORY).exists()
    snap(data, "auto", 8)
    bf.export_snapshots(data, target, bf.MODE_APP)
    bf.rotate(target, keep_history=True)
    assert len(names(daily)) == 7 and len(names(target / bf.HISTORY / "giornalieri")) == 1


def test_manual_copies_are_never_rotated(data, target) -> None:
    for day in range(12):
        snap(data, "manual", day)
    bf.export_snapshots(data, target, bf.MODE_APP)
    assert bf.rotate(target) == [] and len(names(bf.tier_dir(target, "manual"))) == 12


def test_taking_over_sets_aside_the_users_files_without_deleting_them(data, target) -> None:
    snap(data, "manual", 0)
    bf.export_snapshots(data, target, bf.MODE_APP)
    mine = target / "miei" / "vecchio.zbbackup"
    mine.parent.mkdir(parents=True)
    mine.write_bytes(b"x")
    (target / "note.txt").write_text("non toccare")
    other = target / "vecchio.zbbackup"
    other.write_bytes(b"y")
    kinds = {item.path.name: item.kind for item in bf.list_files(target)}
    assert kinds["vecchio.zbbackup"] == "altri"
    moved = bf.take_over(target)
    assert len(moved) == 2 and all(bf.SET_ASIDE in path.parts for path in moved)
    assert (target / "note.txt").read_text() == "non toccare"
    assert not other.exists() and not mine.exists()
    assert {item.kind for item in bf.list_files(target)} == {"manual", "gestione"}


def test_an_imported_file_is_copied_not_moved(data, target, tmp_path) -> None:
    snap(data, "manual", 0)
    source = bundle.export_bundle(data, backups.list_snapshots(data)[0].id, tmp_path / "x" / "fuori.zbbackup")
    copy = bf.keep_imported_copy(target, source)
    assert copy is not None and copy.parent.name == bf.IMPORTED and source.exists()
    assert bf.keep_imported_copy(target, source) is None  # already there


def test_changing_folder_moves_only_the_apps_own_files(data, target, tmp_path) -> None:
    snap(data, "auto", 0)
    bf.export_snapshots(data, target, bf.MODE_APP)
    (target / "mio.zbbackup").write_bytes(b"x")
    new = tmp_path / "nuova"
    moved = bf.move_scheme(target, new)
    assert len(moved) == 1 and (target / "mio.zbbackup").exists()
    assert [item.kind for item in bf.list_files(new)] == ["auto"]


def test_remembered_folders_that_are_gone_are_not_shown(tmp_path) -> None:
    here = tmp_path / "qui"
    here.mkdir()
    assert bf.existing([str(here), str(tmp_path / "sparita"), str(here), ""]) == [str(here)]


def test_a_folder_the_system_refuses_gives_a_plain_message_not_errno(data, target, monkeypatch) -> None:
    snap(data, "manual", 0)

    def refuse(*args, **kwargs):
        raise PermissionError(1, "Operation not permitted", str(target))

    monkeypatch.setattr(bundle, "export_bundle", refuse)
    with pytest.raises(bf.FolderWriteError) as caught:
        bf.export_snapshots(data, target, bf.MODE_APP)
    message = str(caught.value)
    assert "permesso" in message and "salvo" in message and "Errno" not in message
    assert bf._done(data, target) == []  # nothing is marked as written: the next save tries again


def test_another_write_failure_keeps_the_reason_and_says_the_work_is_safe(data, target, monkeypatch) -> None:
    snap(data, "manual", 0)
    monkeypatch.setattr(bundle, "export_bundle", lambda *a, **k: (_ for _ in ()).throw(OSError(28, "No space left on device")))
    with pytest.raises(bf.FolderWriteError, match="No space left on device.*salvo"):
        bf.export_snapshots(data, target, bf.MODE_APP)


# * — opaque files (KAN-29): a flat folder of random names, what each one is lives in the private index —

PASSPHRASE = "cavallo batteria graffetta"


@pytest.fixture
def sealed(data, monkeypatch) -> Path:
    monkeypatch.setattr(keys, "DEFAULT_SCRYPT_PARAMS", ScryptParams(n=2**10))
    keys.setup_keys(data, PASSPHRASE)
    return data


def test_opaque_files_are_flat_with_random_names_and_the_index_knows_them(sealed, target) -> None:
    snap(sealed, "auto", 0)
    snap(sealed, "week", 1)
    snap(sealed, "pre-restore", 2)  # not a kind the folder keeps
    written = bf.export_snapshots(sealed, target, bf.MODE_APP)
    assert len(written) == 2 and all(path.parent == target and not path.name.startswith("zibaldone-") for path in written)
    assert sorted(path.name for path in target.iterdir()) == sorted(path.name for path in written)  # no subfolders
    assert bf.export_snapshots(sealed, target, bf.MODE_APP) == []
    listed = bf.list_files(target, sealed)
    assert [item.kind for item in listed] == ["week", "auto"] and listed[0].created_at > listed[1].created_at
    assert all(bundle.inspect_bundle(item.path, passphrase=PASSPHRASE).ok for item in listed)
    assert {item.kind for item in bf.list_files(target)} == {"altri"}  # without the index nothing tells them apart


def test_opaque_rotation_keeps_seven_daily_by_the_index(sealed, target) -> None:
    for day in range(8):
        snap(sealed, "auto", day)
        bf.export_snapshots(sealed, target, bf.MODE_APP)
    oldest = bf.list_files(target, sealed)[-1].path
    gone = bf.rotate(target, folder=sealed)
    assert gone == [oldest] and not oldest.exists() and len(bf.list_files(target, sealed)) == 7
    assert bf.export_snapshots(sealed, target, bf.MODE_APP) == []  # a rotated file is not written again
    snap(sealed, "auto", 8)
    bf.export_snapshots(sealed, target, bf.MODE_APP)
    [kept] = bf.rotate(target, keep_history=True, folder=sealed)
    assert kept.exists() and [item.kind for item in bf.list_files(target, sealed)].count("storico") == 1


def test_files_of_the_old_scheme_get_an_opaque_copy_and_go_only_when_the_user_asks(data, target, monkeypatch) -> None:
    snap(data, "auto", 0)
    snap(data, "manual", 1)
    bf.export_snapshots(data, target, bf.MODE_APP)  # no keys yet: the scheme before, in clear
    old = sorted(path for path in target.rglob("*.zbbackup"))
    (target / "mio.zbbackup").write_bytes(b"x")
    monkeypatch.setattr(keys, "DEFAULT_SCRYPT_PARAMS", ScryptParams(n=2**10))
    keys.setup_keys(data, PASSPHRASE)
    written = bf.export_snapshots(data, target, bf.MODE_APP)
    assert len(written) == 2 and all(not bundle.is_zip(path) for path in written)
    kinds = sorted(item.kind for item in bf.list_files(target, data))
    assert kinds == ["altri", "auto", "manual", bf.OLD_FORMAT, bf.OLD_FORMAT]
    assert bf.export_snapshots(data, target, bf.MODE_APP) == []  # the same snapshots are not written twice
    assert all(bundle.inspect_bundle(path, passphrase=PASSPHRASE).ok for path in written)  # the old zip opens from inside
    deleted = bf.delete_old_format(data, target)
    assert sorted(deleted) == old and not (target / bf.ROOT).exists() and (target / "mio.zbbackup").exists()


def test_deleting_one_file_from_the_app_is_remembered(sealed, target) -> None:
    snap(sealed, "manual", 0)
    [path] = bf.export_snapshots(sealed, target, bf.MODE_APP)
    bf.delete_file(sealed, target, path)
    assert not path.exists() and bf.list_files(target, sealed) == []
    assert bf.export_snapshots(sealed, target, bf.MODE_APP) == []


def test_taking_over_leaves_the_apps_opaque_files_where_they_are(sealed, target) -> None:
    snap(sealed, "manual", 0)
    [path] = bf.export_snapshots(sealed, target, bf.MODE_APP)
    (target / "vecchio.zbbackup").write_bytes(b"y")
    moved = bf.take_over(target, sealed)
    assert [item.name for item in moved] == ["vecchio.zbbackup"] and path.exists()


def test_an_imported_file_becomes_an_opaque_copy_in_the_index(sealed, target, tmp_path) -> None:
    snap(sealed, "manual", 0)
    outside = bundle.export_bundle(sealed, backups.list_snapshots(sealed)[0].id, tmp_path / "x" / "fuori.zbbackup")
    copy = bf.keep_imported_copy(target, outside, sealed)
    assert copy is not None and copy.parent == target and outside.exists() and copy.read_bytes() == outside.read_bytes()
    assert [item.kind for item in bf.list_files(target, sealed)] == ["importati"]


def test_changing_folder_brings_the_opaque_files_and_their_index(sealed, target, tmp_path) -> None:
    snap(sealed, "auto", 0)
    [path] = bf.export_snapshots(sealed, target, bf.MODE_APP)
    new = tmp_path / "nuova"
    moved = bf.move_scheme(target, new, sealed)
    assert moved == [new / path.name] and bf.index_of(sealed, target) == {}
    assert [item.kind for item in bf.list_files(new, sealed)] == ["auto"]
    assert bf.export_snapshots(sealed, new, bf.MODE_APP) == []
