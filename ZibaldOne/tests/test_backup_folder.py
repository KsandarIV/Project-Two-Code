"""The visible folder of backup files (0.3.3): subfolders by kind, rotation, the user's files set aside."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from zibaldone.core.templates import BlockSpec, Template
from zibaldone.storage import backup_folder as bf
from zibaldone.storage import backups, bundle
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
