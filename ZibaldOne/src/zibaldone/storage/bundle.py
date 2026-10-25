"""The backup file (`.zbbackup`, 0.3.1): one snapshot with everything it needs, to carry away and bring back.

It is a zip with no compression (what is inside is already encrypted) holding:

- `bundle.json`: format, snapshot name, time, versions, whether it is encrypted, the attached files it needs;
- `<id>.zbsnap`: the snapshot as it is in `backups/`;
- `media/<file>.zbblob`: the sealed copies of its attached files;
- `keys.json` (when encryption is on): the public key and the private key already locked by passphrase and
  recovery code, so the passphrase works on a new device too. Nothing in it opens the backup by itself.

Importing never overwrites: the snapshot and the files are added next to the others, `keys.json` is installed
only when this device has none, and the data is replaced only by `restore_bundle`, after the usual checks.
"""

import json
import os
import secrets
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from zibaldone import __version__
from zibaldone.core.blocks import MEDIA_FILE
from zibaldone.core.crypto import CryptoError
from zibaldone.storage import backups, keys
from zibaldone.storage.backups import BackupError, KeyRequiredError, RestoreResult, SnapshotInfo
from zibaldone.storage.database import MIGRATIONS, database_path
from zibaldone.storage.keys import KeysError

BUNDLE_SUFFIX = ".zbbackup"
BUNDLE_FORMAT = "zibaldone-backup"
BUNDLE_FORMAT_VERSION = 1
INFO_FILE = "bundle.json"
MEDIA_DIR = "media/"
MAX_MEMBER_SIZE = backups.MAX_SNAPSHOT_FILE_SIZE
NOT_A_BACKUP = "questo file non è un backup di ZibaldOne"


@dataclass
class BundleInfo:
    """What a backup file says about itself, read without opening its content."""

    path: Path
    snapshot_id: str = ""
    created_at: Optional[datetime] = None
    encrypted: bool = False
    app_version: str = ""
    schema_version: Optional[int] = None
    media: List[str] = field(default_factory=list)
    has_keys: bool = False
    problems: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


@dataclass
class ImportResult:
    snapshot: SnapshotInfo
    keys_installed: bool  # this device had no keys.json and took the one in the file
    other_key: bool  # this device has other keys: only the recovery code opens the snapshot


# * — export —


def export_bundle(folder: Path, reference: str, destination: Path) -> Path:
    """Write the backup file of one snapshot. `destination` is a file ending in .zbbackup, or a folder (made if missing) where the file is named after the snapshot's time."""
    snapshot = backups.find_snapshot(folder, reference)
    if snapshot.problem:
        raise BackupError(f"l'istantanea {snapshot.id} non si legge: {snapshot.problem}")
    target = destination if destination.suffix == BUNDLE_SUFFIX else destination / f"zibaldone-{snapshot.created_at.strftime('%Y-%m-%d-%H%M')}{BUNDLE_SUFFIX}"
    info = {
        "format": BUNDLE_FORMAT,
        "format_version": BUNDLE_FORMAT_VERSION,
        "app_version": __version__,
        "snapshot": snapshot.path.name,
        "id": snapshot.id,
        "created_at": snapshot.created_at.isoformat(),
        "encrypted": snapshot.encrypted,
        "schema_version": snapshot.schema_version,
        "media": snapshot.media,
        "keys": keys.is_configured(folder),
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f"{backups.TEMP_PREFIX}{secrets.token_hex(4)}")
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_STORED) as archive:
            archive.writestr(INFO_FILE, json.dumps(info, indent=2))
            archive.write(snapshot.path, snapshot.path.name)
            for file in snapshot.media:
                blob = backups.blob_path(folder, file)
                if not blob.exists():
                    raise BackupError(f"nei backup manca l'allegato {file[:8]}")
                archive.write(blob, f"{MEDIA_DIR}{file}{backups.BLOB_SUFFIX}")
            if info["keys"]:
                archive.write(keys.keys_path(folder), keys.KEYS_FILE)
        os.replace(temporary, target)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return target


# * — reading —


def _member(archive: zipfile.ZipFile, name: str) -> bytes:
    info = archive.getinfo(name)
    if info.file_size > MAX_MEMBER_SIZE:
        raise BackupError("il file contiene una parte troppo grande")
    return archive.read(name)


def inspect_bundle(path: Path) -> BundleInfo:
    """Check the shape of a backup file without importing or decrypting anything."""
    result = BundleInfo(path=Path(path))
    try:
        with zipfile.ZipFile(path) as archive:
            infos = {item.filename: item for item in archive.infolist()}
            if INFO_FILE not in infos:
                result.problems.append(NOT_A_BACKUP)
                return result
            if any(item.compress_type != zipfile.ZIP_STORED for item in infos.values()):
                result.problems.append("il file ha una forma che ZibaldOne non produce")
                return result
            description = json.loads(_member(archive, INFO_FILE).decode("utf-8"))
            if not isinstance(description, dict) or description.get("format") != BUNDLE_FORMAT:
                result.problems.append(NOT_A_BACKUP)
                return result
            if description.get("format_version") != BUNDLE_FORMAT_VERSION:
                result.problems.append("questo backup viene da una versione di ZibaldOne con un formato diverso: aggiorna l'app")
                return result
            name = description.get("snapshot")
            match = backups.SNAPSHOT_NAME.match(name) if isinstance(name, str) else None
            if not match or name not in infos:
                result.problems.append("nel file manca l'istantanea")
                return result
            result.snapshot_id = name[: -len(backups.SNAPSHOT_SUFFIX)]
            result.created_at = datetime.strptime(match.group(1), backups.ID_TIME_FORMAT).replace(tzinfo=timezone.utc)
            result.encrypted = description.get("encrypted") is True
            result.app_version = str(description.get("app_version") or "")
            schema = description.get("schema_version")
            result.schema_version = schema if isinstance(schema, int) and not isinstance(schema, bool) else None
            if result.schema_version is not None and result.schema_version > len(MIGRATIONS):
                result.problems.append(f"backup di una versione più recente di ZibaldOne (schema {result.schema_version}): aggiorna l'app")
            result.media = backups.media_list(description.get("media"))
            for file in result.media:
                if f"{MEDIA_DIR}{file}{backups.BLOB_SUFFIX}" not in infos:
                    result.problems.append(f"nel file manca l'allegato {file[:8]}")
            result.has_keys = keys.KEYS_FILE in infos
            allowed = {INFO_FILE, name, keys.KEYS_FILE, *(f"{MEDIA_DIR}{file}{backups.BLOB_SUFFIX}" for file in result.media)}
            if set(infos) - allowed:
                result.problems.append("il file contiene parti che non dovrebbero esserci")
            for item in infos.values():
                if item.file_size > MAX_MEMBER_SIZE:
                    result.problems.append("il file contiene una parte troppo grande")
                    break
    except (OSError, zipfile.BadZipFile, ValueError, KeyError, BackupError) as error:
        result.problems.append(NOT_A_BACKUP if isinstance(error, (zipfile.BadZipFile, ValueError, KeyError)) else str(error))
    return result


# * — finding a backup file at first start (0.3.1) —

SEARCH_FOLDERS = ("Downloads", "Download", "Documents", "Documenti", "Desktop", "Scrivania")
MAX_FILES_LOOKED_AT = 200


def default_search_dirs() -> List[Path]:
    """Where people leave a file they exported: the usual folders of their home."""
    home = Path.home()
    return [home / name for name in SEARCH_FOLDERS if (home / name).is_dir()]


def find_backup_files(directories: Optional[List[Path]] = None) -> List[BundleInfo]:
    """The valid backup files in these folders (not their subfolders), the newest backup first. Never raises."""
    found: List[BundleInfo] = []
    for directory in default_search_dirs() if directories is None else directories:
        try:
            files = sorted(Path(directory).glob(f"*{BUNDLE_SUFFIX}"))[:MAX_FILES_LOOKED_AT]
        except OSError:
            continue
        for path in files:
            info = inspect_bundle(path)
            if info.ok and path.is_file():
                found.append(info)
    return sorted(found, key=lambda info: (info.created_at, info.snapshot_id), reverse=True)


def first_run_candidate(folder: Path, directories: Optional[List[Path]] = None) -> Optional[BundleInfo]:
    """The backup file to offer on a new installation, or None.

    Only when this device has no data and no snapshot of its own: with either of them there is nothing to bring back
    (and what is there must not be replaced without being asked).
    """
    if database_path(folder).exists() or backups.has_local_backup(folder):
        return None
    files = find_backup_files(directories)
    return files[0] if files else None


# * — import and restore —


def _keys_document(data: bytes) -> str:
    try:
        key_id = json.loads(data.decode("utf-8"))["key_id"]
    except (UnicodeDecodeError, ValueError, KeyError, TypeError):
        raise BackupError("il file delle chiavi nel backup è rovinato") from None
    if not isinstance(key_id, str):
        raise BackupError("il file delle chiavi nel backup è rovinato")
    return key_id


def _install_keys(folder: Path, data: bytes) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    path = keys.keys_path(folder)
    temporary = path.with_name(f".{keys.KEYS_FILE}.import")
    temporary.write_bytes(data)
    try:
        os.chmod(temporary, 0o600)
    except OSError:
        pass  # Windows: the data folder is already private to the user
    os.replace(temporary, path)
    try:
        keys.key_id(folder)  # validates the format and the public key
    except KeysError as error:
        path.unlink(missing_ok=True)
        raise BackupError(f"il file delle chiavi nel backup non è valido: {error}") from None


def import_bundle(folder: Path, path: Path) -> ImportResult:
    """Add the snapshot, its attached files and (if this device has none) the keys of a backup file. Replaces no data."""
    description = inspect_bundle(path)
    if not description.ok:
        raise BackupError("; ".join(description.problems))
    name = f"{description.snapshot_id}{backups.SNAPSHOT_SUFFIX}"
    directory = backups.backups_dir(folder)
    directory.mkdir(parents=True, exist_ok=True)
    keys_installed = other_key = False
    try:
        with zipfile.ZipFile(path) as archive:
            blobs = {file: _member(archive, f"{MEDIA_DIR}{file}{backups.BLOB_SUFFIX}") for file in description.media if not backups.blob_path(folder, file).exists()}
            snapshot_bytes = _member(archive, name) if not (directory / name).exists() else None
            bundle_keys = _member(archive, keys.KEYS_FILE) if description.has_keys else None
            if bundle_keys is not None:
                bundle_key_id = _keys_document(bundle_keys)
                if not keys.is_configured(folder):
                    _install_keys(folder, bundle_keys)
                    keys_installed = True
                else:
                    other_key = keys.key_id(folder) != bundle_key_id
    except (OSError, zipfile.BadZipFile) as error:
        raise BackupError(f"non riesco a leggere il file: {error}") from None
    for file, data in blobs.items():
        backups._atomic_write(backups.blob_path(folder, file), data)
    if snapshot_bytes is not None:
        backups._atomic_write(directory / name, snapshot_bytes)
    return ImportResult(snapshot=backups.find_snapshot(folder, description.snapshot_id), keys_installed=keys_installed, other_key=other_key)


def restore_bundle(folder: Path, path: Path, passphrase: Optional[str] = None, recovery_code: Optional[str] = None) -> RestoreResult:
    """Import a backup file and bring the data back to it, undoably (as `backups.restore_snapshot`). Close every Store first."""
    imported = import_bundle(folder, path)
    snapshot = imported.snapshot
    private_key = None
    if snapshot.encrypted:
        try:
            if recovery_code:
                if keys.is_configured(folder) and not imported.other_key:
                    private_key = keys.unlock_with_recovery_code(folder, recovery_code)
                else:
                    private_key = backups.unlock_snapshot_with_recovery_code(folder, snapshot.id, recovery_code)
            elif passphrase:
                if imported.other_key or not keys.is_configured(folder):
                    raise BackupError("questo backup si apre solo con il codice di recupero")
                private_key = keys.unlock_with_passphrase(folder, passphrase)
            else:
                raise KeyRequiredError("serve la passphrase dei backup o il codice di recupero")
        except (KeysError, CryptoError) as error:
            raise BackupError(str(error)) from None
    return backups.restore_snapshot(folder, snapshot.id, private_key)

