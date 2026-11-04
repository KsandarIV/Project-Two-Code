"""The encrypted database (KAN-107): whoever knows the path of the data folder reads nothing.

On disk the database is `zibaldone.zbdb`: `ZBDB` + version + nonce + AES-256-GCM of the whole SQLite file. It is
opened in memory only (`sqlite3` deserialize), and written back, encrypted, when a Store that changed it closes.
One copy in memory per data folder, shared by every Store of the process and guarded by a lock: two Stores never
work on two copies, so nothing is lost between threads. Two processes at once (the app and `zbone`) are not
coordinated: the last one that saves wins (known limit, written in docs/tecnica/backup.md).

The 32-byte key lives in the system keystore (the app, `flet-secure-storage`) and, sealed to the backup public key,
in keys.json (`database_key`): the main password or the recovery code bring it back on a new install.
The key is registered here for the process with `unlock`; it is never written to disk by this module.
"""

import os
import secrets
import sqlite3
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from zibaldone.core.errors import StoreError

SEALED_FILE = "zibaldone.zbdb"
MAGIC = b"ZBDB"
VERSION = 1
HEADER = MAGIC + bytes([VERSION])
NONCE_SIZE = 12
KEY_SIZE = 32


class DatabaseLockedError(StoreError):
    """The database is encrypted and its key is not known yet: the main password opens it."""


@dataclass
class _Memory:
    connection: sqlite3.Connection
    lock: threading.RLock = field(default_factory=threading.RLock)
    saved_changes: int = 0


_keys: Dict[Path, bytes] = {}
_memories: Dict[Path, _Memory] = {}
_guard = threading.Lock()


def sealed_path(folder: Path) -> Path:
    return folder / SEALED_FILE


def is_sealed(folder: Path) -> bool:
    return sealed_path(folder).exists()


def new_key() -> bytes:
    return secrets.token_bytes(KEY_SIZE)


def _folder(folder: Path) -> Path:
    return Path(folder).resolve()


def encrypt(key: bytes, data: bytes) -> bytes:
    nonce = secrets.token_bytes(NONCE_SIZE)
    return HEADER + nonce + AESGCM(key).encrypt(nonce, data, HEADER)


def decrypt(key: bytes, blob: bytes) -> bytes:
    if not blob.startswith(HEADER) or len(blob) < len(HEADER) + NONCE_SIZE + 16:
        raise StoreError("il database cifrato è rovinato o viene da una versione diversa di ZibaldOne")
    nonce = blob[len(HEADER) : len(HEADER) + NONCE_SIZE]
    try:
        return AESGCM(key).decrypt(nonce, blob[len(HEADER) + NONCE_SIZE :], HEADER)
    except InvalidTag:
        raise StoreError("la chiave del database non è quella giusta, oppure il file è rovinato") from None


def _write(path: Path, blob: bytes) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    with open(temporary, "wb") as handle:
        handle.write(blob)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.chmod(temporary, 0o600)
    except OSError:
        pass
    os.replace(temporary, path)


def unlock(folder: Path, key: bytes) -> None:
    """Register the key for this process; checked at once when the file exists."""
    if len(key) != KEY_SIZE:
        raise StoreError("chiave del database di misura sbagliata")
    where = _folder(folder)
    if sealed_path(where).exists():
        decrypt(key, sealed_path(where).read_bytes())
    with _guard:
        _keys[where] = key


def is_unlocked(folder: Path) -> bool:
    return _folder(folder) in _keys


def key_of(folder: Path) -> bytes:
    """The key registered for this folder (to copy into keys.json or the keystore)."""
    return _key(_folder(folder))


def forget(folder: Optional[Path] = None) -> None:
    """Drop the key and the copy in memory (one folder, or all: tests)."""
    with _guard:
        targets = [_folder(folder)] if folder is not None else list(set(_keys) | set(_memories))
        for where in targets:
            _keys.pop(where, None)
            memory = _memories.pop(where, None)
            if memory is not None:
                memory.connection.close()


def _key(where: Path) -> bytes:
    key = _keys.get(where)
    if key is None:
        raise DatabaseLockedError("il database è cifrato: serve la password principale per aprirlo")
    return key


def acquire(folder: Path) -> sqlite3.Connection:
    """The shared connection of this folder, locked for the caller until `release`."""
    where = _folder(folder)
    with _guard:
        key = _key(where)
        memory = _memories.get(where)
        if memory is None:
            connection = sqlite3.connect(":memory:", check_same_thread=False)
            path = sealed_path(where)
            if path.exists():
                connection.deserialize(decrypt(key, path.read_bytes()))
            memory = _memories[where] = _Memory(connection, saved_changes=connection.total_changes)
    memory.lock.acquire()
    return memory.connection


def release(folder: Path) -> None:
    """Save the copy in memory when it changed, then let the next Store in."""
    where = _folder(folder)
    memory = _memories.get(where)
    if memory is None:
        return
    try:
        if memory.connection.total_changes != memory.saved_changes:
            save(where)
    finally:
        memory.lock.release()


def save(folder: Path) -> None:
    """Write the copy in memory to disk, encrypted. The caller holds the lock (or nobody else can)."""
    where = _folder(folder)
    memory = _memories[where]
    with memory.lock:
        _write(sealed_path(where), encrypt(_key(where), memory.connection.serialize()))
        memory.saved_changes = memory.connection.total_changes


def plain_bytes(folder: Path) -> bytes:
    """The database as a plain SQLite file, for snapshots."""
    connection = acquire(folder)
    try:
        return connection.serialize()
    finally:
        release(folder)


def replace(folder: Path, sqlite_file: Path) -> None:
    """Put a plain SQLite file (a restored snapshot) in place, encrypted, and reload the copy in memory."""
    where = _folder(folder)
    key = _key(where)
    data = Path(sqlite_file).read_bytes()
    with _guard:
        memory = _memories.pop(where, None)
    if memory is not None:
        with memory.lock:
            memory.connection.close()
    _write(sealed_path(where), encrypt(key, data))


def seal_plain(folder: Path, plain_file: Path, key: bytes) -> None:
    """Encrypt an existing plain database once, check it opens, then remove the plain file and its journals."""
    source = sqlite3.connect(str(plain_file))
    try:
        data = source.serialize()
    finally:
        source.close()
    where = _folder(folder)
    blob = encrypt(key, data)
    if decrypt(key, blob) != data:
        raise StoreError("la cifratura del database non torna: non ho toccato il database in chiaro")
    _write(sealed_path(where), blob)
    with _guard:
        _keys[where] = key
    for suffix in ("", "-wal", "-shm", "-journal"):
        try:
            Path(f"{plain_file}{suffix}").unlink()
        except FileNotFoundError:
            pass
