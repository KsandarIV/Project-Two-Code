"""Mimesis (0.2.4): files attached to entries, stored once, kept in the (encrypted) backups and in the cloud copies."""

import os
import time
from datetime import timedelta
from pathlib import Path

import pytest
from typer.testing import CliRunner

from zibaldone.cli.app import app
from zibaldone.cloud import sync
from zibaldone.cloud.destinations import LocalFolderDestination
from zibaldone.core.blocks import BLOCK_TYPES, media_kind
from zibaldone.core.crypto import ScryptParams
from zibaldone.core.privacy import NOTICE_VERSION
from zibaldone.core.templates import Template
from zibaldone.storage import backups, keys, media
from zibaldone.storage.database import Store, StoreError
from zibaldone.storage.paths import data_dir
from zibaldone.storage.settings import record_consent

PASSPHRASE = "cavallo batteria graffetta"
PHOTO = b"\x89PNG una foto del mare"
AUDIO = b"ID3 una nota vocale"
ALBUM = Template.from_dict(
    {"slug": "ricordo", "name": "Ricordo", "blocks": [{"key": "titolo", "type": "text", "label": "Titolo"}, {"key": "file", "type": "media", "label": "Allegati"}]}
)
runner = CliRunner()


@pytest.fixture(autouse=True)
def fast_scrypt(monkeypatch):
    monkeypatch.setattr(keys, "DEFAULT_SCRYPT_PARAMS", ScryptParams(n=2**10))


def age(path: Path, hours: float = 2) -> None:
    """Make a file look old enough to be cleaned up."""
    past = time.time() - hours * 3600
    os.utime(path, (past, past))


def remember(folder: Path, title: str, *files: tuple) -> str:
    with Store.open(folder) as store:
        if store.find_template("ricordo") is None:
            store.save_template(ALBUM)
        attached = [media.add_bytes(folder, name, data).to_value() for name, data in files]
        return store.add_entry("ricordo", {"titolo": title, "file": attached}).id


def test_the_block_names_files_and_never_holds_them() -> None:
    block = BLOCK_TYPES["media"]
    item = {"file": "a" * 64 + ".jpg", "name": "mare.jpg", "size": 3}
    assert block.normalize([item, dict(item)], {}) == [item]  # the same file once
    assert block.to_text([item], {}) == "mare.jpg"
    for wrong in ([{"file": "../x", "name": "x", "size": 1}], [{**item, "name": "cartella/mare.jpg"}], [{**item, "size": -1}], "mare.jpg"):
        with pytest.raises(ValueError):
            block.normalize(wrong, {})
    with pytest.raises(ValueError, match="al massimo 1"):
        block.normalize([item, {**item, "file": "b" * 64}], {"max_items": 1})
    with pytest.raises(ValueError, match="zbone allegati aggiungi"):
        block.parse("mare.jpg", {})
    assert [media_kind(name) for name in ("A.JPG", "v.mp4", "n.m4a", "referto.pdf", "senza")] == ["foto", "video", "audio", "documento", "documento"]


def test_stored_once_checked_on_save_and_cleaned_up_later(isolated_data_dir) -> None:
    folder = isolated_data_dir
    first, again = media.add_bytes(folder, "mare.JPG", PHOTO), media.add_bytes(folder, "copia.jpg", PHOTO)
    assert first.file == again.file and media.stored_files(folder) == [first.file] and first.file.endswith(".jpg")
    with pytest.raises(media.MediaError, match="troppo grande"):
        media.add_bytes(folder, "enorme.mp4", b"x" * (media.MAX_MEDIA_BYTES + 1))
    entry_id = remember(folder, "Estate", ("mare.jpg", PHOTO))
    with Store.open(folder) as store:
        with pytest.raises(StoreError, match="non è nella cartella"):
            store.add_entry("ricordo", {"file": [{"file": "c" * 64, "name": "fantasma", "size": 1}]})
        store.delete_entry(entry_id)
        assert media.stored_files(folder) == [first.file]  # just added: kept for an hour
        age(media.path_of(folder, first.file))
        assert store.remove_unused_media() == [first.file] and media.stored_files(folder) == []


def test_snapshots_keep_the_files_and_a_restore_brings_them_back(isolated_data_dir) -> None:
    folder = isolated_data_dir
    remember(folder, "Estate", ("mare.jpg", PHOTO), ("voce.m4a", AUDIO))
    snapshot = backups.create_snapshot(folder)
    files = media.stored_files(folder)
    assert sorted(snapshot.media) == files and all(backups.blob_path(folder, file).read_bytes() in (PHOTO, AUDIO) for file in files)
    assert backups.create_snapshot(folder).media == snapshot.media  # stored once, not per snapshot
    for file in files:
        media.path_of(folder, file).unlink()
    backups.restore_snapshot(folder, snapshot.id)
    assert media.read(folder, files[0]) in (PHOTO, AUDIO) and media.stored_files(folder) == files
    backups.blob_path(folder, files[0]).write_bytes(b"rovinato")
    assert any("rovinato" in problem for problem in backups.verify_snapshot(folder, snapshot.id).problems)


def test_encrypted_backups_seal_the_files_and_prune_what_no_snapshot_needs(isolated_data_dir) -> None:
    folder = isolated_data_dir
    remember(folder, "Prima", ("mare.jpg", PHOTO))
    plain = backups.create_snapshot(folder)
    main = keys.setup_keys(folder, PASSPHRASE).private_key
    result = backups.encrypt_existing_snapshots(folder, main)
    assert result.failed == [] and plain.id in result.encrypted
    blob = backups.blob_path(folder, plain.media[0])
    assert PHOTO not in blob.read_bytes() and backups.blob_bytes(folder, plain.media[0], main) == PHOTO
    with pytest.raises(backups.KeyRequiredError):
        backups.blob_bytes(folder, plain.media[0], None)
    assert backups.verify_snapshot(folder, plain.id, main).ok
    entry_id = remember(folder, "Dopo", ("voce.m4a", AUDIO))
    later = backups.create_snapshot(folder, now=plain.created_at + timedelta(minutes=5))  # a later second, so the order is certain
    assert backups.list_snapshots(folder)[0].media == later.media  # read from the public header, no passphrase
    with Store.open(folder) as store:
        store.delete_entry(entry_id)
    for path in [*backups.blob_files(folder).values(), *(media.path_of(folder, file) for file in media.stored_files(folder))]:
        age(path)
    with Store.open(folder) as store:
        store.remove_unused_media()
    newest = backups.create_snapshot(folder, now=later.created_at.replace(year=2099))
    later.path.unlink()  # as if retention had dropped it
    backups.prune(folder, backups.RetentionPolicy(daily=5, weekly=0, monthly=0))
    assert set(backups.blob_files(folder)) == set(newest.media) | set(plain.media) and len(backups.blob_files(folder)) == 1


def test_cloud_copies_carry_the_files_to_a_new_device(isolated_data_dir, tmp_path) -> None:
    stick = tmp_path / "chiavetta"
    stick.mkdir()
    old = tmp_path / "vecchio-pc"
    remember(old, "Estate", ("mare.jpg", PHOTO))
    keys.setup_keys(old, PASSPHRASE)
    backups.create_snapshot(old)
    destination = LocalFolderDestination(stick)
    stray = "d" * 64 + ".jpg" + backups.BLOB_SUFFIX
    destination.upload(stray, b"di nessuno")
    result = sync.sync_now(old, destination)
    assert len(result.media_uploaded) == 1 and result.media_deleted == ["d" * 64 + ".jpg"]
    assert "1 allegati caricati" in result.message
    names = [item.name for item in destination.list_files()]
    assert stray not in names and all(PHOTO not in (stick / "ZibaldOne" / name).read_bytes() for name in names)
    sync.recover_from_cloud(isolated_data_dir, passphrase=PASSPHRASE, destination=destination)
    assert [media.read(isolated_data_dir, file) for file in media.stored_files(isolated_data_dir)] == [PHOTO]
    assert sync.forget_remote(old, destination) == len(names)


def test_cli_attach_show_save_and_remove(isolated_data_dir, tmp_path) -> None:
    record_consent(data_dir(), accepted=True, notice_version=NOTICE_VERSION)
    entry_id = remember(data_dir(), "Estate")
    photo = tmp_path / "mare.jpg"
    photo.write_bytes(PHOTO)
    added = runner.invoke(app, ["allegati", "aggiungi", entry_id[:8], str(photo)])
    assert added.exit_code == 0 and "Allegati a «Estate»: mare.jpg" in added.output, added.output
    shown = runner.invoke(app, ["allegati", "mostra", entry_id[:8]])
    assert "1. mare.jpg · foto" in shown.output, shown.output
    out = tmp_path / "copie"
    runner.invoke(app, ["allegati", "salva", entry_id[:8], "--in", str(out)])
    runner.invoke(app, ["allegati", "salva", entry_id[:8], "1", "--in", str(out)])
    assert sorted(path.name for path in out.iterdir()) == ["mare (2).jpg", "mare.jpg"] and (out / "mare.jpg").read_bytes() == PHOTO
    assert "Allegati: 1 file" in runner.invoke(app, ["allegati"]).output
    assert runner.invoke(app, ["entry", "add", "ricordo", "--set", "file=mare.jpg"]).exit_code == 1
    removed = runner.invoke(app, ["allegati", "togli", entry_id[:8], "1"])
    assert removed.exit_code == 0 and "Tolto «mare.jpg»" in removed.output
    assert runner.invoke(app, ["allegati", "togli", entry_id[:8], "1"]).exit_code == 1
