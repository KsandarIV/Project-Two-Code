"""Snapshots of the user's data, like commits: create, list, restore, verify, prune.

A snapshot is one file in `<data folder>/backups/`, named after its UTC time,
for example `20261017T112233Z-a1b2c3.zbsnap`. It is a zip with:

- `manifest.json`: id, time, app version, schema version, reason, note,
  SHA-256 and size of the database, number of entries and templates;
- `zibaldone.db`: a consistent copy made with SQLite's backup API;
- `settings.json`: a copy of the settings, for reference.

Once encryption is set up (`keys.json`, v0.0.7) the zip is sealed to the backup
public key (`core/crypto.py`) and never written in clear. The public header
repeats only id, time, reason and versions, plus the recovery-code wrap, so a
single file copied elsewhere can be opened with the recovery code alone.
Notes and counts stay inside the encrypted part.

**What a restore brings back and what it keeps.** A restore replaces only the
database: templates and entries return exactly as they were. `settings.json`
(privacy consent, backup policy, later the account and cloud choices) and
`keys.json` describe this device and the user's current decisions, so they
are kept: an old snapshot must never revoke a consent, change the retention
(which would delete snapshots) or bring back an old passphrase. The copy of
`settings.json` stays inside the snapshot for inspection and for moving to a
new device (v0.0.8).

Before restoring, the current state is saved as a "pre-restore" snapshot, so
a restore can be undone. Callers must close every `Store` on the folder
first: see `restore_snapshot`.

**Attached files (0.2.4).** The files in `media/` are kept once each, next to
the snapshots, as `<file>.zbblob` (sealed like the snapshots once encryption
is on). A snapshot lists the files it needs in its manifest and, for an
encrypted one, in its public header too, so pruning can tell without the
passphrase which copies no snapshot needs any more. A restore puts back the
files that are missing.
"""

import hashlib
import io
import json
import os
import re
import secrets
import sqlite3
import tempfile
import time
import zipfile
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone, tzinfo
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey

from zibaldone import __version__
from zibaldone.core import crypto
from zibaldone.core.crypto import CryptoError
from zibaldone.core.blocks import MEDIA_FILE
from zibaldone.storage import keys, media
from zibaldone.storage.database import DATABASE_FILE, MIGRATIONS, database_path
from zibaldone.storage.keys import KeysError
from zibaldone.storage.settings import SETTINGS_FILE, SettingsError, load_settings, save_settings, settings_path

BACKUPS_DIR = "backups"
SNAPSHOT_SUFFIX = ".zbsnap"
SNAPSHOT_NAME = re.compile(r"^(\d{8}T\d{6}Z)-([0-9a-f]{6})\.zbsnap$")
ID_TIME_FORMAT = "%Y%m%dT%H%M%SZ"
SNAPSHOT_FORMAT = "zibaldone-snapshot"
SNAPSHOT_FORMAT_VERSION = 1
MANIFEST_FILE = "manifest.json"
BLOB_SUFFIX = ".zbblob"
PUBLIC_FIELDS = ("format", "format_version", "id", "created_at", "app_version", "schema_version", "reason")

REASONS = ("manual", "auto", "week", "month", "year", "pre-restore", "pre-migration")
REASON_LABELS = {
    "manual": "manuale",
    "auto": "automatica",
    "week": "della settimana",
    "month": "del mese",
    "year": "dell'anno",
    "pre-restore": "prima di un ripristino",
    "pre-migration": "prima di un aggiornamento",
}
MAX_NOTE_LENGTH = 200
MAX_SNAPSHOT_SIZE = crypto.MAX_PAYLOAD_SIZE
MAX_SNAPSHOT_FILE_SIZE = MAX_SNAPSHOT_SIZE + crypto.MAX_HEADER_SIZE + 1024

TEMP_PREFIX = ".zbtmp-"
STALE_TEMP_SECONDS = 3600

SETTINGS_KEY = "backup"
DEFAULT_AUTO = True
AUTO_HOUR = 1  # local time: the daily copy is made at the first chance after 01:00
# The automatic scheme (0.3.1): one copy of today, overwritten every day; then one of the week, of the month and of
# the year, each kept up to its limit and replacing the oldest. Copies made by hand are never removed by the app.
TIERS = ("week", "month", "year")
TIER_DAYS = {"week": 7, "month": 28, "year": 365}
TIER_KEEP = {"week": 4, "month": 3, "year": 3}
SCHEME_KEYS = ("since", "current", "current_id", *TIERS)

IN_USE = "il database è in uso da un altro programma o finestra di ZibaldOne: chiudila e riprova"


class BackupError(Exception):
    """A backup operation failed or was refused. Messages are for the user."""


class KeyRequiredError(BackupError):
    """The snapshot is encrypted and no unlocked private key was given."""


# * — settings —


@dataclass
class BackupSettings:
    """`auto`: the automatic scheme is on (the default); off means manual, and the user looks after the copies.
    `scheme` remembers when each automatic copy was made; `pending_remote` the copies removed here that a
    destination outside the device should lose too (`cloud/sync.py`)."""

    auto: bool = DEFAULT_AUTO
    scheme: Dict[str, str] = field(default_factory=dict)
    pending_remote: List[str] = field(default_factory=list)


def _validated(backup: BackupSettings) -> BackupSettings:
    if not isinstance(backup.auto, bool):
        raise BackupError(f"{SETTINGS_FILE}: '{SETTINGS_KEY}.auto' deve essere true o false")
    return backup


def load_backup_settings(folder: Path) -> BackupSettings:
    """Keys of the older retention settings (days, weeks, interval) are ignored."""
    try:
        data = load_settings(folder).get(SETTINGS_KEY, {})
    except SettingsError as error:
        raise BackupError(str(error)) from None
    if not isinstance(data, dict):
        raise BackupError(f"{SETTINGS_FILE}: '{SETTINGS_KEY}' deve essere un oggetto")
    scheme = data.get("scheme")
    pending = data.get("pending_remote")
    return _validated(
        BackupSettings(
            auto=data.get("auto", DEFAULT_AUTO),
            scheme={key: value for key, value in scheme.items() if key in SCHEME_KEYS and isinstance(value, str)} if isinstance(scheme, dict) else {},
            pending_remote=[item for item in pending if isinstance(item, str)] if isinstance(pending, list) else [],
        )
    )


def save_backup_settings(folder: Path, backup: BackupSettings) -> None:
    """Write the `backup` key of settings.json, keeping every other setting."""
    _validated(backup)
    try:
        settings = load_settings(folder)
    except SettingsError as error:
        raise BackupError(str(error)) from None
    settings[SETTINGS_KEY] = {"auto": backup.auto, "scheme": backup.scheme, "pending_remote": backup.pending_remote}
    save_settings(folder, settings)


# * — results —


@dataclass
class SnapshotInfo:
    """What is known about a snapshot. For an encrypted one, `note` and the
    counts are None until it is read with the private key."""

    id: str
    path: Path
    created_at: datetime
    size: int
    encrypted: bool = False
    reason: str = ""
    app_version: str = ""
    schema_version: Optional[int] = None
    note: Optional[str] = None
    entries: Optional[int] = None
    templates: Optional[int] = None
    problem: str = ""
    media: List[str] = field(default_factory=list)  # attached files it needs (0.2.4)

    @property
    def reason_label(self) -> str:
        return REASON_LABELS.get(self.reason, self.reason or "sconosciuto")


@dataclass
class VerifyResult:
    snapshot: SnapshotInfo
    problems: List[str]

    @property
    def ok(self) -> bool:
        return not self.problems


@dataclass
class RestoreResult:
    restored: SnapshotInfo
    undo: Optional[SnapshotInfo]  # the "pre-restore" snapshot; None if there was no database


@dataclass
class PruneResult:
    keep: List[SnapshotInfo]
    remove: List[SnapshotInfo]
    why: Dict[str, List[str]]  # snapshot id -> rules that keep it
    dry_run: bool = False
    failed: List[Tuple[str, str]] = field(default_factory=list)


@dataclass
class EncryptionResult:
    encrypted: List[str]
    failed: List[Tuple[str, str]]


# * — small file helpers —


def backups_dir(folder: Path) -> Path:
    return folder / BACKUPS_DIR


def _utc(now: Optional[datetime] = None) -> datetime:
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        raise ValueError("serve un orario con fuso orario")
    return moment.astimezone(timezone.utc).replace(microsecond=0)


def _new_temp_path(directory: Path, suffix: str = "") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(prefix=TEMP_PREFIX, suffix=suffix, dir=directory)
    os.close(handle)
    return Path(name)


def _remove_quietly(path: Optional[Path]) -> None:
    if path is None:
        return
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def _fsync_directory(directory: Path) -> None:
    if os.name != "posix":
        return
    handle = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(handle)
    except OSError:
        pass
    finally:
        os.close(handle)


def _atomic_write(path: Path, data: bytes) -> None:
    temporary = _new_temp_path(path.parent)
    try:
        with open(temporary, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        _remove_quietly(temporary)
    _fsync_directory(path.parent)


def _remove_stale_temp_files(folder: Path) -> None:
    """Temporary copies left by a crash may hold plain data: remove them after an hour."""
    limit = time.time() - STALE_TEMP_SECONDS
    for directory in (folder, backups_dir(folder)):
        if not directory.is_dir():
            continue
        for path in directory.glob(TEMP_PREFIX + "*"):
            try:
                if path.is_file() and path.stat().st_mtime < limit:
                    path.unlink()
            except OSError:
                pass


# * — reading snapshots —


def _snapshot_files(folder: Path) -> List[Tuple[str, datetime, Path]]:
    """(id, UTC time, path) of every snapshot, from file names only (cheap)."""
    directory = backups_dir(folder)
    if not directory.is_dir():
        return []
    found = []
    for path in directory.iterdir():
        match = SNAPSHOT_NAME.match(path.name)
        if not match or not path.is_file():
            continue
        try:
            created = datetime.strptime(match.group(1), ID_TIME_FORMAT).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        found.append((path.name[: -len(SNAPSHOT_SUFFIX)], created, path))
    return found


def _apply_fields(info: SnapshotInfo, fields: Any, private: bool) -> None:
    if not isinstance(fields, dict):
        raise BackupError("descrizione dell'istantanea mancante")
    info.reason = str(fields.get("reason", ""))
    info.app_version = str(fields.get("app_version", ""))
    schema = fields.get("schema_version")
    info.schema_version = schema if isinstance(schema, int) else None
    if private:
        info.media = media_list(fields.get("media"))
        info.note = str(fields.get("note", ""))
        counts = fields.get("counts") if isinstance(fields.get("counts"), dict) else {}
        info.entries, info.templates = counts.get("entries"), counts.get("templates")


def _read_manifest(archive_source: Any) -> Dict[str, Any]:
    with zipfile.ZipFile(archive_source) as archive:
        manifest = json.loads(archive.read(MANIFEST_FILE).decode("utf-8"))
    if not isinstance(manifest, dict) or manifest.get("format") != SNAPSHOT_FORMAT:
        raise BackupError("manifest.json non valido")
    return manifest


def _describe(snapshot_id: str, created: datetime, path: Path, private_key: Optional[X25519PrivateKey] = None) -> SnapshotInfo:
    info = SnapshotInfo(id=snapshot_id, path=path, created_at=created, size=path.stat().st_size)
    try:
        with open(path, "rb") as handle:
            info.encrypted = crypto.is_sealed(handle.read(len(crypto.MAGIC)))
            handle.seek(0)
            if not info.encrypted:
                _apply_fields(info, _read_manifest(handle), private=True)
            elif private_key is None:
                header = crypto.read_sealed_header(handle)
                _apply_fields(info, header.get("snapshot"), private=False)
                info.media = media_list(header.get("media"))
        if info.encrypted and private_key is not None:
            sealed = crypto.open_sealed(_read_snapshot_bytes(path), private_key)
            _apply_fields(info, _read_manifest(io.BytesIO(sealed.plaintext)), private=True)
    except (BackupError, CryptoError) as error:
        info.problem = str(error)
    except (zipfile.BadZipFile, zlib.error, KeyError, ValueError, OSError, EOFError) as error:
        info.problem = f"file rovinato o illeggibile ({error})"
    return info


def _sort_key(info: SnapshotInfo) -> Tuple[datetime, str]:
    return info.created_at, info.id


def list_snapshots(folder: Path, private_key: Optional[X25519PrivateKey] = None) -> List[SnapshotInfo]:
    """Every snapshot, newest first. With the private key, encrypted notes and counts too."""
    infos = [_describe(snapshot_id, created, path, private_key) for snapshot_id, created, path in _snapshot_files(folder)]
    return sorted(infos, key=_sort_key, reverse=True)


def find_snapshot(folder: Path, reference: str) -> SnapshotInfo:
    """Find a snapshot by full id, by the start of the id or by its 6-character code."""
    wanted = reference.strip().lower().removesuffix(SNAPSHOT_SUFFIX)
    files = _snapshot_files(folder)
    matches = [item for item in files if item[0].lower() == wanted]
    if not matches and len(wanted) >= 4:
        matches = [item for item in files if item[0].lower().startswith(wanted) or item[0].lower().split("-")[1].startswith(wanted)]
    if not matches:
        raise BackupError(f"nessuna istantanea '{reference}'. Vedi `zbone backup list`")
    if len(matches) > 1:
        raise BackupError(f"più istantanee corrispondono a '{reference}': scrivi qualche carattere in più")
    return _describe(*matches[0])


def _read_snapshot_bytes(path: Path) -> bytes:
    if path.stat().st_size > MAX_SNAPSHOT_FILE_SIZE:
        raise BackupError("istantanea troppo grande (massimo 1 GiB)")
    return path.read_bytes()


# * — attached files (0.2.4) —


def media_list(value: Any) -> List[str]:
    """The attached files named by a manifest or header; [] for snapshots before 0.2.4."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and MEDIA_FILE.match(item)]


def blob_path(folder: Path, file: str) -> Path:
    return backups_dir(folder) / f"{file}{BLOB_SUFFIX}"


def blob_files(folder: Path) -> Dict[str, Path]:
    """Attached file name -> its copy in the backups."""
    directory = backups_dir(folder)
    if not directory.is_dir():
        return {}
    found = {}
    for path in directory.iterdir():
        if path.name.endswith(BLOB_SUFFIX) and MEDIA_FILE.match(path.name[: -len(BLOB_SUFFIX)]) and path.is_file():
            found[path.name[: -len(BLOB_SUFFIX)]] = path
    return found


def _is_sealed_file(path: Path) -> bool:
    with open(path, "rb") as handle:
        return crypto.is_sealed(handle.read(len(crypto.MAGIC)))


def _store_blobs(folder: Path, files: Iterable[str], recipient: Optional[X25519PublicKey]) -> None:
    """Copy each attached file next to the snapshots once; sealed once encryption is on."""
    for file in files:
        path = blob_path(folder, file)
        if path.exists() and (recipient is None or _is_sealed_file(path)):
            continue
        try:
            data = media.read(folder, file)
        except media.MediaError as error:
            raise BackupError(str(error)) from None
        _atomic_write(path, data if recipient is None else crypto.seal(data, recipient, {"media": file}))


def blob_bytes(folder: Path, file: str, private_key: Optional[X25519PrivateKey]) -> bytes:
    """The attached file kept in the backups, checked against its SHA-256."""
    path = blob_path(folder, file)
    try:
        data = path.read_bytes()
    except OSError:
        raise BackupError(f"nei backup manca l'allegato {file[:8]}") from None
    if crypto.is_sealed(data):
        if private_key is None:
            raise KeyRequiredError("gli allegati dei backup sono cifrati: serve la passphrase")
        sealed = crypto.open_sealed(data, private_key)
        if sealed.header.get("media") != file:
            raise BackupError(f"l'allegato {file[:8]} nei backup non corrisponde al suo nome")
        data = sealed.plaintext
    if hashlib.sha256(data).hexdigest() != file[:64]:
        raise BackupError(f"l'allegato {file[:8]} nei backup è rovinato")
    return data


def _media_problems(folder: Path, manifest: Dict[str, Any], header: Optional[Dict[str, Any]], private_key: Optional[X25519PrivateKey]) -> List[str]:
    files = media_list(manifest.get("media"))
    problems = []
    if header is not None and media_list(header.get("media")) != files:
        problems.append("l'elenco degli allegati nell'intestazione non corrisponde al contenuto cifrato")
    for file in files:
        try:
            blob_bytes(folder, file, private_key)
        except KeyRequiredError:
            continue  # a plain snapshot made before encryption: its files are already sealed
        except (BackupError, CryptoError) as error:
            problems.append(str(error))
    return problems


def _restore_media(folder: Path, files: Iterable[str], private_key: Optional[X25519PrivateKey]) -> None:
    for file in files:
        if not media.path_of(folder, file).exists():
            media.add_bytes(folder, file, blob_bytes(folder, file, private_key))


def _remove_unused_blobs(folder: Path, now: Optional[float] = None) -> List[str]:
    """Delete the copies of attached files that no snapshot needs any more (older than an hour)."""
    snapshots = list_snapshots(folder)
    if any(info.problem for info in snapshots):
        return []  # a snapshot that cannot be read might need any of them
    needed = {file for info in snapshots for file in info.media}
    limit = (now or time.time()) - STALE_TEMP_SECONDS
    removed = []
    for file, path in blob_files(folder).items():
        try:
            if file not in needed and path.stat().st_mtime < limit:
                path.unlink()
                removed.append(file)
        except OSError:
            continue
    return removed


# * — creating —


@dataclass
class _DatabaseCopy:
    data: bytes
    schema_version: int
    entries: Optional[int]
    templates: Optional[int]


def _count(connection: sqlite3.Connection, table: str) -> Optional[int]:
    try:
        return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    except sqlite3.OperationalError:
        return None  # table not created yet (schema 0)


def _copy_database(folder: Path, db: Path) -> _DatabaseCopy:
    """A consistent copy through SQLite's backup API, never a copy of the live file."""
    if db.stat().st_size > MAX_SNAPSHOT_SIZE:
        raise BackupError("il database è troppo grande per un'istantanea (massimo 1 GiB)")
    temporary = _new_temp_path(folder, ".db")
    try:
        source = sqlite3.connect(str(db))
        try:
            target = sqlite3.connect(str(temporary))
            try:
                source.backup(target)
                schema = target.execute("PRAGMA user_version").fetchone()[0]
                entries, templates = _count(target, "entries"), _count(target, "templates")
            finally:
                target.close()
        finally:
            source.close()
        return _DatabaseCopy(temporary.read_bytes(), schema, entries, templates)
    except sqlite3.Error as error:
        raise BackupError(f"non riesco a copiare il database: {error}") from None
    finally:
        _remove_quietly(temporary)


def _build_archive(manifest: Dict[str, Any], database: bytes, settings: Optional[bytes], created: datetime) -> bytes:
    stamp = created.timetuple()[:6]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        members = [(MANIFEST_FILE, json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8")), (DATABASE_FILE, database)]
        if settings is not None:
            members.append((SETTINGS_FILE, settings))
        for name, data in members:
            member = zipfile.ZipInfo(name, date_time=stamp)
            member.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(member, data)
    return buffer.getvalue()


def _has_encrypted_snapshots(folder: Path) -> bool:
    for _, _, path in _snapshot_files(folder):
        try:
            with open(path, "rb") as handle:
                if crypto.is_sealed(handle.read(len(crypto.MAGIC))):
                    return True
        except OSError:
            continue
    return False


def _encryption_target(folder: Path) -> Optional[X25519PublicKey]:
    """The public key to seal to, or None before encryption is set up.

    Never silently falls back to plain snapshots once encrypted ones exist.
    """
    if keys.is_configured(folder):
        try:
            return keys.load_public_key(folder)
        except (KeysError, CryptoError) as error:
            raise BackupError(f"non posso cifrare l'istantanea: {error}") from None
    if _has_encrypted_snapshots(folder):
        raise BackupError(
            "ci sono istantanee cifrate ma manca keys.json nella cartella dati: non salvo copie in chiaro. "
            "Rimetti il file al suo posto"
        )
    return None


def _seal_archive(folder: Path, archive: bytes, manifest: Dict[str, Any], recipient: X25519PublicKey) -> bytes:
    try:
        fields = {
            "snapshot": {name: manifest[name] for name in PUBLIC_FIELDS},
            "recovery_wrap": keys.recovery_wrap(folder),
            "media": media_list(manifest.get("media")),
        }
        return crypto.seal(archive, recipient, fields)
    except (KeysError, CryptoError) as error:
        raise BackupError(f"non posso cifrare l'istantanea: {error}") from None


def _clean_note(note: str) -> str:
    text = " ".join((note or "").split())
    if len(text) > MAX_NOTE_LENGTH:
        raise BackupError(f"la nota può avere al massimo {MAX_NOTE_LENGTH} caratteri")
    return text


def create_snapshot(folder: Path, reason: str = "manual", note: str = "", now: Optional[datetime] = None) -> SnapshotInfo:
    """Save a full, consistent copy of the data; encrypted once keys.json exists."""
    if reason not in REASONS:
        raise ValueError(f"motivo sconosciuto: {reason}")
    note = _clean_note(note)
    db = database_path(folder)
    if not db.exists():
        raise BackupError("non ci sono ancora dati da salvare: aggiungi prima un modello o una voce")
    recipient = _encryption_target(folder)
    created = _utc(now)
    snapshot_id = f"{created.strftime(ID_TIME_FORMAT)}-{secrets.token_hex(3)}"
    _remove_stale_temp_files(folder)
    copy = _copy_database(folder, db)
    files = media.stored_files(folder)
    _store_blobs(folder, files, recipient)
    manifest = {
        "format": SNAPSHOT_FORMAT,
        "format_version": SNAPSHOT_FORMAT_VERSION,
        "id": snapshot_id,
        "created_at": created.isoformat(),
        "app_version": __version__,
        "schema_version": copy.schema_version,
        "reason": reason,
        "note": note,
        "database": {"file": DATABASE_FILE, "sha256": hashlib.sha256(copy.data).hexdigest(), "size": len(copy.data)},
        "counts": {"entries": copy.entries, "templates": copy.templates},
        "media": files,
    }
    settings_file = settings_path(folder)
    archive = _build_archive(manifest, copy.data, settings_file.read_bytes() if settings_file.exists() else None, created)
    if len(archive) > MAX_SNAPSHOT_SIZE:
        raise BackupError("l'istantanea supera 1 GiB")
    content = archive if recipient is None else _seal_archive(folder, archive, manifest, recipient)
    path = backups_dir(folder) / f"{snapshot_id}{SNAPSHOT_SUFFIX}"
    _atomic_write(path, content)
    return SnapshotInfo(
        id=snapshot_id,
        path=path,
        created_at=created,
        size=len(content),
        encrypted=recipient is not None,
        reason=reason,
        app_version=__version__,
        schema_version=copy.schema_version,
        note=note,
        entries=copy.entries,
        templates=copy.templates,
        media=files,
    )


# * — checking —


@dataclass
class _Inspection:
    problems: List[str]
    manifest: Dict[str, Any] = field(default_factory=dict)
    database_path: Optional[Path] = None  # checked copy, to delete or move into place


def _open_payload(data: bytes, private_key: Optional[X25519PrivateKey]) -> Tuple[bytes, Optional[Dict[str, Any]]]:
    if not crypto.is_sealed(data):
        return data, None
    if private_key is None:
        raise KeyRequiredError("questa istantanea è cifrata: serve la passphrase")
    sealed = crypto.open_sealed(data, private_key)
    return sealed.plaintext, sealed.header


def _unpack(archive_bytes: bytes) -> Tuple[Dict[str, Any], bytes]:
    try:
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            missing = [name for name in (MANIFEST_FILE, DATABASE_FILE) if name not in archive.namelist()]
            if missing:
                raise BackupError(f"nell'istantanea mancano: {', '.join(missing)}")
            if any(member.file_size > MAX_SNAPSHOT_SIZE for member in archive.infolist()):
                raise BackupError("contenuto dell'istantanea troppo grande")
            damaged = archive.testzip()
            if damaged:
                raise BackupError(f"'{damaged}' nell'istantanea è rovinato")
            manifest = json.loads(archive.read(MANIFEST_FILE).decode("utf-8"))
            database = archive.read(DATABASE_FILE)
    except (zipfile.BadZipFile, zlib.error, EOFError, UnicodeDecodeError, ValueError, NotImplementedError, RuntimeError) as error:
        raise BackupError(f"l'istantanea è rovinata ({error})") from None
    if not isinstance(manifest, dict) or manifest.get("format") != SNAPSHOT_FORMAT:
        raise BackupError("manifest.json non valido")
    return manifest, database


def _manifest_problems(manifest: Dict[str, Any], database: bytes, snapshot_id: str, header: Optional[Dict[str, Any]]) -> List[str]:
    problems = []
    version = manifest.get("format_version")
    if not isinstance(version, int) or version > SNAPSHOT_FORMAT_VERSION:
        problems.append("formato dell'istantanea più recente o sconosciuto: aggiorna ZibaldOne")
    if manifest.get("id") != snapshot_id:
        problems.append("il nome del file non corrisponde all'istantanea")
    described = manifest.get("database") if isinstance(manifest.get("database"), dict) else {}
    if described.get("sha256") != hashlib.sha256(database).hexdigest() or described.get("size") != len(database):
        problems.append("l'impronta (SHA-256) del database non corrisponde: istantanea alterata o rovinata")
    schema = manifest.get("schema_version")
    if isinstance(schema, bool) or not isinstance(schema, int) or schema < 0:
        problems.append("versione dello schema mancante")
    elif schema > len(MIGRATIONS):
        problems.append(f"istantanea di una versione più recente di ZibaldOne (schema {schema}): aggiorna l'app")
    if header is not None:
        public = header.get("snapshot") if isinstance(header.get("snapshot"), dict) else {}
        if any(public.get(name) != manifest.get(name) for name in PUBLIC_FIELDS):
            problems.append("l'intestazione non corrisponde al contenuto cifrato")
    return problems


def _database_problems(path: Path, expected_schema: Any) -> List[str]:
    try:
        connection = sqlite3.connect(str(path))
        try:
            result = [row[0] for row in connection.execute("PRAGMA integrity_check").fetchall()]
            schema = connection.execute("PRAGMA user_version").fetchone()[0]
        finally:
            connection.close()
    except sqlite3.DatabaseError as error:
        return [f"il database dell'istantanea non si apre ({error})"]
    problems = []
    if result != ["ok"]:
        problems.append("il database dell'istantanea non è integro: " + "; ".join(str(line) for line in result[:3]))
    if schema != expected_schema:
        problems.append("la versione dello schema del database non corrisponde al manifest")
    return problems


def _inspect_bytes(folder: Path, snapshot_id: str, data: bytes, private_key: Optional[X25519PrivateKey]) -> _Inspection:
    """Decrypt, unpack and check. The checked database is left in a temporary file."""
    try:
        archive, header = _open_payload(data, private_key)
        manifest, database = _unpack(archive)
    except KeyRequiredError:
        raise
    except (BackupError, CryptoError) as error:
        return _Inspection(problems=[str(error)])
    problems = _manifest_problems(manifest, database, snapshot_id, header) + _media_problems(folder, manifest, header, private_key)
    temporary = _new_temp_path(folder, ".db")
    try:
        with open(temporary, "wb") as handle:
            handle.write(database)
            handle.flush()
            os.fsync(handle.fileno())
        problems += _database_problems(temporary, manifest.get("schema_version"))
    except BaseException:
        _remove_quietly(temporary)
        raise
    return _Inspection(problems=problems, manifest=manifest, database_path=temporary)


def _inspect(folder: Path, snapshot: SnapshotInfo, private_key: Optional[X25519PrivateKey]) -> _Inspection:
    try:
        data = _read_snapshot_bytes(snapshot.path)
    except OSError as error:
        return _Inspection(problems=[f"non riesco a leggere il file: {error}"])
    return _inspect_bytes(folder, snapshot.id, data, private_key)


def verify_snapshot(folder: Path, reference: str, private_key: Optional[X25519PrivateKey] = None) -> VerifyResult:
    """Zip integrity, authenticated decryption, SHA-256, `PRAGMA integrity_check`, schema version.

    Raises KeyRequiredError for an encrypted snapshot without `private_key`.
    """
    snapshot = find_snapshot(folder, reference)
    inspection = _inspect(folder, snapshot, private_key)
    _remove_quietly(inspection.database_path)
    return VerifyResult(snapshot=snapshot, problems=inspection.problems)


# * — restoring —


def _ensure_database_idle(db: Path) -> None:
    """Refuse while another connection holds a lock; also settles a hot journal."""
    try:
        connection = sqlite3.connect(str(db), timeout=0.5, isolation_level=None)
        try:
            connection.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()
            connection.execute("BEGIN EXCLUSIVE")
            connection.execute("ROLLBACK")
        finally:
            connection.close()
    except sqlite3.OperationalError:
        raise BackupError(IN_USE) from None
    except sqlite3.DatabaseError:
        pass  # a broken database can still be replaced by a good snapshot
    if any(db.with_name(db.name + suffix).exists() for suffix in ("-journal", "-wal")):
        raise BackupError(IN_USE)


def restore_snapshot(folder: Path, reference: str, private_key: Optional[X25519PrivateKey] = None) -> RestoreResult:
    """Bring templates and entries back to a snapshot; settings.json and keys.json stay.

    The snapshot is fully checked first, then the current database is saved as
    a "pre-restore" snapshot (the undo point), then replaced atomically
    (temporary file + os.replace). Close every `Store` on `folder` before
    calling: the file is swapped underneath, and a connection left open would
    keep reading or writing the old one. That is why this function takes a
    folder, not a Store. A connection busy in a transaction is detected and
    refused.
    """
    snapshot = find_snapshot(folder, reference)
    inspection = _inspect(folder, snapshot, private_key)
    try:
        if inspection.problems:
            raise BackupError(f"l'istantanea {snapshot.id} non è integra: {'; '.join(inspection.problems)}")
        db = database_path(folder)
        undo = None
        if db.exists():
            _ensure_database_idle(db)
            undo = create_snapshot(folder, "pre-restore")
        _restore_media(folder, media_list(inspection.manifest.get("media")), private_key)
        try:
            os.replace(inspection.database_path, db)
        except OSError as error:
            raise BackupError(f"non riesco a sostituire il database ({error}). {IN_USE}") from None
        _fsync_directory(folder)
        return RestoreResult(restored=snapshot, undo=undo)
    finally:
        _remove_quietly(inspection.database_path)


def unlock_snapshot_with_recovery_code(folder: Path, reference: str, recovery_code: str) -> X25519PrivateKey:
    """Open an encrypted snapshot without keys.json (for example on a new device),
    using the recovery wrap stored in its header."""
    snapshot = find_snapshot(folder, reference)
    try:
        with open(snapshot.path, "rb") as handle:
            header = crypto.read_sealed_header(handle)
    except OSError as error:
        raise BackupError(f"non riesco a leggere il file: {error}") from None
    wrap = header.get("recovery_wrap")
    if not isinstance(wrap, dict):
        raise BackupError("questa istantanea non contiene la chiave per il codice di recupero")
    return keys.unlock_recovery_wrap(wrap, header["recipient"], recovery_code)


# * — what to keep —


def plan_retention(snapshots: Iterable[SnapshotInfo], protect: Iterable[str] = ()) -> PruneResult:
    """Decide what the automatic scheme keeps.

    Kept: the newest automatic copy (today's), the newest copies of the week, of the month and of the year up to
    their limits (`TIER_KEEP`), every copy made by hand, the newest "prima di un ripristino" and the newest "prima
    di un aggiornamento", whatever cannot be classified (a file that does not read), the ids in `protect` and the
    most recent snapshot of all. The rest goes: the copy of yesterday that today's replaces, a fifth weekly one.
    """
    ordered = sorted(snapshots, key=_sort_key, reverse=True)
    why: Dict[str, List[str]] = {item.id: [] for item in ordered}
    if ordered:
        why[ordered[0].id].append("la più recente")
    for reason, limit, label in (("auto", 1, "di oggi"), ("pre-restore", 1, "annulla l'ultimo ripristino"), ("pre-migration", 1, "prima dell'ultimo aggiornamento"), *((tier, TIER_KEEP[tier], REASON_LABELS[tier]) for tier in TIERS)):
        for item in [item for item in ordered if item.reason == reason][:limit]:
            why[item.id].append(label)
    for item in ordered:
        if item.reason == "manual" or item.reason not in REASONS:
            why[item.id].append("fatta a mano" if item.reason == "manual" else "da non toccare")
    for snapshot_id in protect:
        if snapshot_id in why:
            why[snapshot_id].append("appena creata")
    keep = [item for item in ordered if why[item.id]]
    remove = [item for item in ordered if not why[item.id]]
    return PruneResult(keep=keep, remove=remove, why={key: value for key, value in why.items() if value})


def prune(folder: Path, dry_run: bool = False, protect: Iterable[str] = ()) -> PruneResult:
    """Delete the snapshots the automatic scheme no longer keeps. What is removed is remembered for the destinations outside the device."""
    plan = plan_retention(list_snapshots(folder), protect)
    plan.dry_run = dry_run
    if not dry_run:
        removed = []
        for item in plan.remove:
            try:
                item.path.unlink()
                removed.append(item.id)
            except FileNotFoundError:
                removed.append(item.id)
            except OSError as error:
                plan.failed.append((item.id, str(error)))
        _remove_unused_blobs(folder)
        if removed:
            backup = load_backup_settings(folder)
            backup.pending_remote = [*backup.pending_remote, *(item for item in removed if item not in backup.pending_remote)]
            save_backup_settings(folder, backup)
    return plan


# * — automatic snapshots —


def _cutoff(now: datetime, tz: Optional[tzinfo]) -> datetime:
    """The latest 01:00 (local time) that is not after `now`."""
    local = now.astimezone(tz)
    at = local.replace(hour=AUTO_HOUR, minute=0, second=0, microsecond=0)
    return (at if local >= at else at - timedelta(days=1)).astimezone(timezone.utc)


def _when(value: Optional[str]) -> Optional[datetime]:
    try:
        moment = datetime.fromisoformat(value) if value else None
    except ValueError:
        return None
    return moment if moment is None or moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def maybe_auto_snapshot(folder: Path, now: Optional[datetime] = None, tz: Optional[tzinfo] = None) -> Optional[SnapshotInfo]:
    """The automatic scheme, to call when the app opens and after commands that write data.

    Only when automatic backups are on (the default), the database exists and today's copy is missing (none yet
    since the last 01:00) does it make a new "of today" copy; the one of yesterday goes. A copy of the week, of
    the month or of the year is added when 7, 28 or 365 days have passed since the last one (or since the first
    automatic copy); each tier keeps its newest few. Copies made by hand are never touched.
    Cheap when there is nothing to do: reads settings.json only. Returns today's new snapshot, or None;
    raises BackupError only on a real failure, which the caller should show as a warning without failing the command.
    """
    backup = load_backup_settings(folder)
    if not backup.auto or not database_path(folder).exists():
        return None
    current = _utc(now)
    scheme = backup.scheme
    made = _when(scheme.get("current"))
    if made is not None and made <= current and made >= _cutoff(current, tz) and (backups_dir(folder) / f"{scheme.get('current_id', '')}{SNAPSHOT_SUFFIX}").exists():
        return None  # a stamp from the future (clock changed) does not count: the copy is made again
    snapshot = create_snapshot(folder, "auto", now=current)
    protect = [snapshot.id]
    scheme["since"] = scheme.get("since") or current.isoformat()
    for tier in TIERS:
        last = _when(scheme.get(tier)) or _when(scheme["since"])
        if last is None or last > current:  # no stamp, or one from the future: count from now
            scheme[tier] = current.isoformat()
        elif current - last >= timedelta(days=TIER_DAYS[tier]):
            protect.append(create_snapshot(folder, tier, now=current).id)
            scheme[tier] = current.isoformat()
    scheme["current"], scheme["current_id"] = current.isoformat(), snapshot.id
    save_backup_settings(folder, backup)
    prune(folder, protect=protect)
    return snapshot


def maybe_pre_migration_snapshot(folder: Path) -> Optional[SnapshotInfo]:
    """Before `Store.open` migrates an older database, keep a copy of it."""
    db = database_path(folder)
    if not db.exists():
        return None
    try:
        connection = sqlite3.connect(str(db))
        try:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
        finally:
            connection.close()
    except sqlite3.DatabaseError as error:
        raise BackupError(f"non riesco a leggere il database: {error}") from None
    if 0 < version < len(MIGRATIONS):
        return create_snapshot(folder, "pre-migration")
    return None


# * — v0.0.7: encrypting the snapshots made before encryption —


def encrypt_existing_snapshots(folder: Path, private_key: X25519PrivateKey) -> EncryptionResult:
    """Seal every plain snapshot in place, after checking it and its encrypted copy.

    The encrypted file replaces the plain one atomically under the same name,
    so there is never a moment with neither. A plain snapshot that fails its
    check is left untouched and reported, never deleted.
    """
    if not keys.is_configured(folder):
        raise BackupError("prima attiva la cifratura con `zbone backup setup`")
    recipient = _encryption_target(folder)
    if crypto.key_fingerprint(private_key.public_key()) != crypto.key_fingerprint(recipient):
        raise BackupError("la chiave privata non corrisponde a quella dei backup")
    encrypted: List[str] = []
    failed: List[Tuple[str, str]] = []
    for snapshot_id, _, path in sorted(_snapshot_files(folder)):
        try:
            data = _read_snapshot_bytes(path)
        except (OSError, BackupError) as error:
            failed.append((snapshot_id, str(error)))
            continue
        if crypto.is_sealed(data):
            continue
        inspection = _inspect_bytes(folder, snapshot_id, data, None)
        _remove_quietly(inspection.database_path)
        if inspection.problems:
            failed.append((snapshot_id, "; ".join(inspection.problems)))
            continue
        sealed = _seal_archive(folder, data, inspection.manifest, recipient)
        if crypto.open_sealed(sealed, private_key).plaintext != data:
            failed.append((snapshot_id, "la copia cifrata non corrisponde all'originale"))
            continue
        _atomic_write(path, sealed)
        encrypted.append(snapshot_id)
    for file, path in sorted(blob_files(folder).items()):
        try:
            if _is_sealed_file(path):
                continue
            data = blob_bytes(folder, file, None)
            sealed = crypto.seal(data, recipient, {"media": file})
            if crypto.open_sealed(sealed, private_key).plaintext != data:
                raise BackupError("la copia cifrata non corrisponde all'originale")
            _atomic_write(path, sealed)
        except (OSError, BackupError, CryptoError) as error:
            failed.append((f"allegato {file[:8]}", str(error)))
    return EncryptionResult(encrypted=encrypted, failed=failed)
