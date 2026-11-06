"""The folder of backup files the user can see (0.3.3): where each file goes, what is kept, what is left alone.

Inside the folder the user chose, the app keeps its own scheme:

    backup/giornalieri  settimanali  mensili  annuali  manuali
    importati            copies of backup files brought in from outside
    Gestione manuale     the files that were not made by the app, set aside when the app takes over the folder
    Storico              (only when the user asks) what the rotation would have deleted

The app writes, rotates and moves only inside these folders and only `.zbbackup` files. Anything else is not touched.
Files outside the scheme are still listed («Altri») when the user keeps managing them.

**Opaque files (KAN-29).** Once the keys can write opaque backup files (`bundle.opaque_ready`), the folder is flat:
each file has a random name and nothing in the folder says its date or kind. What each file is lives in an index
in the private data folder (`backup_folder_index.json`), which drives the rotation and the list in the app. The
files of the scheme above (the «old format») are wrapped once into opaque copies; the old ones stay until the user
deletes them from the app (`delete_old_format`).
"""

import json
import shutil
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional

from zibaldone.storage import backups, bundle
from zibaldone.storage.bundle import BUNDLE_SUFFIX

MODE_APP = "app"
MODE_USER = "utente"
MODE_MIXED = "misto"
MODES = (MODE_APP, MODE_USER, MODE_MIXED)
MODE_LABELS = {MODE_APP: "Gestisce l'app", MODE_USER: "Gestisco io", MODE_MIXED: "Misto"}

ROOT = "backup"
TIER_DIRS = {"auto": "giornalieri", "week": "settimanali", "month": "mensili", "year": "annuali", "manual": "manuali"}
KEEP = {"auto": 7, "week": 4, "month": 3, "year": 3}  # «manual» is never rotated
IMPORTED = "importati"
SET_ASIDE = "Gestione manuale"
HISTORY = "Storico"
OURS = (ROOT, IMPORTED, SET_ASIDE, HISTORY)
SUGGESTED = "ZibaldOne/Data"


class FolderWriteError(OSError):
    """The visible folder cannot be written. The message is for the user: it says the data is safe and what to do.

    `needs_files_access` is True when the system refused for lack of permission (on Android 11+: «all files access»):
    the UI can then ask for the permission and try again instead of only showing the message.
    """

    def __init__(self, message: str, needs_files_access: bool = False) -> None:
        super().__init__(message)
        self.needs_files_access = needs_files_access


ANDROID_SHARED_STORAGE = ("/storage/", "/sdcard", "/mnt/sdcard")
PROBE = ".zibaldone-prova"


def _on_phone_storage(target: Path) -> bool:
    """The folder is in the shared storage of an Android phone (such folders need «all files access» from Android 11)."""
    return str(target).replace("\\", "/").startswith(ANDROID_SHARED_STORAGE)


def _refused(target: Path) -> FolderWriteError:
    """The sentence for a folder the system will not let the app write, with the way out."""
    if _on_phone_storage(target):
        how = (
            "Su Android serve il permesso «Accesso a tutti i file»: aprilo da Impostazioni del telefono → App → ZibaldOne → Autorizzazioni → "
            "File e contenuti multimediali (o Archiviazione) → Consenti la gestione di tutti i file. "
            "Se non vuoi darlo, scegli una cartella dentro Documenti o Download"
        )
    else:
        how = "Scegli un'altra cartella in Impostazioni → Mnemosyne, o controlla che il tuo utente possa scriverci"
    return FolderWriteError(f"l'app non ha il permesso di scrivere in {target}. Il tuo lavoro è salvo e la copia interna è fatta. {how}.", needs_files_access=True)


@contextmanager
def _explained(target: Optional[Path] = None) -> Iterator[None]:
    """Turn the system's «[Errno 1] Operation not permitted» into a sentence the user can act on (Android refuses some folders)."""
    try:
        yield
    except PermissionError as error:
        raise _refused(target or Path("questa cartella")) from error
    except OSError as error:
        raise FolderWriteError(f"la cartella non si può scrivere ({error.strerror or error}). Il tuo lavoro è salvo e la copia interna è fatta") from error


def check_writable(target: Path) -> None:
    """Try the folder now: make it if needed, write a small file and remove it. Raises FolderWriteError with the way out.

    Use it when the user picks or creates the folder, and before the first backup after an update: on Android the
    folder can exist (chosen with an older version) while the app has no right to write in it.
    """
    with _explained(target):
        target.mkdir(parents=True, exist_ok=True)
        probe = target / PROBE
        probe.write_bytes(b"zibaldone")
        probe.unlink()


OLD_FORMAT = "vecchio"  # a file of the scheme before the opaque files, already wrapped into an opaque copy
REMOVED = "tolto"  # rotated or deleted: remembered so it is not written again


@dataclass(frozen=True)
class FolderFile:
    path: Path
    kind: str  # a TIER_DIRS key, "importati", "gestione", "storico", "altri" or OLD_FORMAT
    created_at: Optional[datetime] = None  # known for the app's opaque files (from the index) and readable old ones


def tier_dir(target: Path, reason: str) -> Path:
    return target / ROOT / TIER_DIRS[reason]


def _name(snapshot: backups.SnapshotInfo) -> str:
    return f"zibaldone-{snapshot.created_at.strftime('%Y-%m-%d-%H%M')}-{snapshot.id}{BUNDLE_SUFFIX}"


LEDGER = "backup_folder_done.json"  # in the private data folder: what was already written, so a file the user (or the rotation) removed is not written again


def _done(folder: Path, target: Path) -> List[str]:
    try:
        value = json.loads((folder / LEDGER).read_text(encoding="utf-8")).get(str(target), [])
    except (OSError, ValueError, AttributeError):
        return []
    return [item for item in value if isinstance(item, str)]


def _remember(folder: Path, target: Path, ids: List[str]) -> None:
    try:
        data = json.loads((folder / LEDGER).read_text(encoding="utf-8"))
        data = data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        data = {}
    data[str(target)] = ids
    (folder / LEDGER).write_text(json.dumps(data, indent=2), encoding="utf-8")


INDEX = "backup_folder_index.json"  # in the private data folder: name -> id, kind, time of each opaque file, per folder


def _index_all(folder: Path) -> Dict[str, Any]:
    try:
        data = json.loads((folder / INDEX).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def index_of(folder: Path, target: Path) -> Dict[str, Dict[str, str]]:
    """What the app knows about the opaque files of `target`: file name -> {"id", "kind", "created_at", "from"?}."""
    entries = _index_all(folder).get(str(target), {})
    if not isinstance(entries, dict):
        return {}
    return {name: entry for name, entry in entries.items() if isinstance(name, str) and isinstance(entry, dict)}


def _save_index(folder: Path, target: Path, entries: Dict[str, Dict[str, str]]) -> None:
    data = _index_all(folder)
    if entries:
        data[str(target)] = entries
    else:
        data.pop(str(target), None)
    (folder / INDEX).write_text(json.dumps(data, indent=2), encoding="utf-8")


def _when(value: Any) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(value) if isinstance(value, str) and value else None
    except ValueError:
        return None


def _old_kind(target: Path, path: Path) -> str:
    """Where a file of the scheme before stands: a TIER_DIRS key, "importati", "gestione", "storico" or "altri"."""
    parts = path.relative_to(target).parts
    by_dir = {name: reason for reason, name in TIER_DIRS.items()}
    if parts[0] == ROOT and len(parts) == 3 and parts[1] in by_dir:
        return by_dir[parts[1]]
    return {IMPORTED: "importati", SET_ASIDE: "gestione", HISTORY: "storico"}.get(parts[0], "altri")


def _wrap_old_files(folder: Path, target: Path, entries: Dict[str, Dict[str, str]]) -> List[Path]:
    """Each file the app wrote in the scheme before (a zip, its date in the name) gets an opaque copy. Needs no passphrase."""
    done = {entry.get("from") for entry in entries.values()}
    written: List[Path] = []
    for path in sorted(target.rglob(f"*{BUNDLE_SUFFIX}")):
        relative = path.relative_to(target).as_posix()
        kind = _old_kind(target, path)
        if kind in ("altri", "gestione") or relative in done or not bundle.is_zip(path):
            continue
        info = bundle.inspect_bundle(path)
        if not info.ok:
            continue
        copy = target / bundle.random_name()
        bundle.write_atomically(copy, bundle.seal(folder, path.read_bytes()))
        entries[copy.name] = {"id": info.snapshot_id, "kind": kind, "created_at": info.created_at.isoformat() if info.created_at else "", "from": relative}
        _save_index(folder, target, entries)
        written.append(copy)
    return written


def _export_opaque(folder: Path, target: Path, mode: str, snapshots: List[backups.SnapshotInfo]) -> List[Path]:
    entries = index_of(folder, target)
    written = _wrap_old_files(folder, target, entries) if target.is_dir() else []
    known = {entry.get("id") for entry in entries.values()}
    chosen = snapshots[:1] if mode == MODE_USER else [info for info in snapshots if info.reason in TIER_DIRS]
    for info in chosen:
        if info.id in known:
            continue
        path = bundle.export_bundle(folder, info.id, target)
        entries[path.name] = {"id": info.id, "kind": "manual" if mode == MODE_USER else info.reason, "created_at": info.created_at.isoformat()}
        _save_index(folder, target, entries)
        written.append(path)
    return written


def export_snapshots(folder: Path, target: Path, mode: str) -> List[Path]:
    """Write the backup files the visible folder has not had yet; returns the new ones.

    «Gestisco io»: the newest snapshot, flat in the folder (the user's way, as before 0.3.3).
    «Gestisce l'app» and «Misto»: every manual, daily, weekly, monthly or yearly snapshot, in its own subfolder.
    Opaque files: the same choice, all flat with random names, recorded in the index.
    """
    snapshots = [info for info in backups.list_snapshots(folder) if not info.problem]
    with _explained(target):
        if bundle.opaque_ready(folder):
            return _export_opaque(folder, target, mode, snapshots)
        if mode == MODE_USER:
            return [bundle.export_bundle(folder, snapshots[0].id, target)] if snapshots else []
        done = _done(folder, target)
        written: List[Path] = []
        for info in snapshots:
            if info.reason not in TIER_DIRS or info.id in done:
                continue
            destination = tier_dir(target, info.reason) / _name(info)
            written.append(bundle.export_bundle(folder, info.id, destination))
            done.append(info.id)
            _remember(folder, target, done)
        return written


def rotate(target: Path, keep_history: bool = False, folder: Optional[Path] = None) -> List[Path]:
    """In each rotating subfolder keep the newest few; the rest is deleted, or moved to «Storico» when asked. Returns what left.

    With `folder`, the app's opaque files are rotated the same way by kind, through the index: a file kept in
    history stays where it is and only changes kind.
    """
    gone: List[Path] = []
    with _explained(target):
        for reason, limit in KEEP.items():
            directory = tier_dir(target, reason)
            files = sorted(directory.glob(f"zibaldone-*{BUNDLE_SUFFIX}"), reverse=True) if directory.is_dir() else []
            for old in files[limit:]:
                if keep_history:
                    destination = target / HISTORY / TIER_DIRS[reason] / old.name
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(old), str(destination))
                else:
                    old.unlink()
                gone.append(old)
        if folder is not None:
            entries = index_of(folder, target)
            for reason, limit in KEEP.items():
                alive = sorted(((entry.get("created_at", ""), name) for name, entry in entries.items() if entry.get("kind") == reason and (target / name).exists()), reverse=True)
                for _, name in alive[limit:]:
                    if keep_history:
                        entries[name]["kind"] = HISTORY.lower()
                    else:
                        (target / name).unlink()
                        entries[name]["kind"] = REMOVED
                    gone.append(target / name)
            if gone:
                _save_index(folder, target, entries)
    return gone


def keep_imported_copy(target: Path, source: Path, folder: Optional[Path] = None) -> Optional[Path]:
    """A copy of a backup file brought in from outside, in «importati»; the original stays where it is.

    With opaque files on (`folder` given), the copy is opaque, flat, with a random name, and goes in the index.
    """
    if source.suffix != BUNDLE_SUFFIX or not source.is_file() or target in source.parents:
        return None
    if folder is not None and bundle.opaque_ready(folder):
        entries = index_of(folder, target)
        info = bundle.inspect_bundle(source)
        data = source.read_bytes()
        destination = target / bundle.random_name()
        bundle.write_atomically(destination, bundle.seal(folder, data) if bundle.is_zip(source) else data)
        entries[destination.name] = {"id": info.snapshot_id, "kind": "importati", "created_at": info.created_at.isoformat() if info.created_at else ""}
        _save_index(folder, target, entries)
        return destination
    destination = target / IMPORTED / source.name
    if destination.exists():
        return None
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return destination


def list_files(target: Path, folder: Optional[Path] = None) -> List[FolderFile]:
    """Every backup file of the folder, told apart by the index (`folder` given) or by where it is. Never raises.

    The app's opaque files come first, newest first. An old-format file that already has its opaque copy is OLD_FORMAT.
    """
    found: List[FolderFile] = []
    entries = index_of(folder, target) if folder is not None else {}
    for name, entry in sorted(entries.items(), key=lambda item: item[1].get("created_at", ""), reverse=True):
        path = target / name
        if entry.get("kind") != REMOVED and path.is_file():
            found.append(FolderFile(path, str(entry.get("kind", "")), _when(entry.get("created_at"))))
    converted = {entry.get("from") for entry in entries.values() if entry.get("from")}
    try:
        candidates = sorted(target.rglob(f"*{BUNDLE_SUFFIX}"))
    except OSError:
        return found
    for path in candidates:
        if path.name in entries and path.parent == target:
            continue
        kind = OLD_FORMAT if path.relative_to(target).as_posix() in converted else _old_kind(target, path)
        found.append(FolderFile(path, kind))
    return found


def delete_old_format(folder: Path, target: Path) -> List[Path]:
    """Delete the old-format files that already have their opaque copy (the user asked, from the app); empty
    subfolders of the old scheme go too. Returns what was deleted."""
    deleted: List[Path] = []
    with _explained(target):
        for item in list_files(target, folder):
            if item.kind == OLD_FORMAT:
                item.path.unlink()
                deleted.append(item.path)
        for name in OURS:
            for directory in sorted((target / name).rglob("*"), reverse=True) + [target / name]:
                if directory.is_dir() and not any(directory.iterdir()):
                    directory.rmdir()
    return deleted


def delete_file(folder: Path, target: Path, path: Path) -> None:
    """Delete one backup file of the folder (the user asked, from the app); the index remembers it so it is not written again."""
    with _explained(path.parent):
        path.unlink(missing_ok=True)
    entries = index_of(folder, target)
    if path.name in entries:
        entries[path.name]["kind"] = REMOVED
        _save_index(folder, target, entries)


def take_over(target: Path, folder: Optional[Path] = None) -> List[Path]:
    """The app starts managing the folder: the files that are not its own go, as they are, to «Gestione manuale».

    Nothing is deleted or renamed; a name already taken gets a number. Returns the new places.
    """
    moved: List[Path] = []
    for item in list_files(target, folder):
        if item.kind != "altri":
            continue
        parts = item.path.relative_to(target).parts
        destination = target / SET_ASIDE / Path(*parts)
        counter = 1
        while destination.exists():
            destination = destination.with_name(f"{item.path.stem}-{counter}{BUNDLE_SUFFIX}")
            counter += 1
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(item.path), str(destination))
        moved.append(destination)
    return moved


def move_scheme(old: Path, new: Path, folder: Optional[Path] = None) -> List[Path]:
    """The folder changes and the user wants the old files along: only the app's own files move, merged into the new place.

    With `folder`, the opaque files of the index move too, and their index entries with them.
    """
    moved: List[Path] = []
    for name in OURS:
        source = old / name
        if not source.is_dir():
            continue
        for path in sorted(source.rglob(f"*{BUNDLE_SUFFIX}")):
            destination = new / path.relative_to(old)
            if destination.exists():
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(destination))
            moved.append(destination)
    if folder is not None:
        entries, arrived = index_of(folder, old), index_of(folder, new)
        for name, entry in entries.items():
            path, destination = old / name, new / name
            if path.is_file() and not destination.exists():
                new.mkdir(parents=True, exist_ok=True)
                shutil.move(str(path), str(destination))
                moved.append(destination)
            arrived.setdefault(name, entry)
        _save_index(folder, new, arrived)
        _save_index(folder, old, {})
    return moved


def existing(paths: Iterable[str]) -> List[str]:
    """The remembered folders that are still there, without repeats: the ones that are gone are not shown."""
    seen: List[str] = []
    for value in paths:
        try:
            if value and value not in seen and Path(value).is_dir():
                seen.append(value)
        except OSError:
            continue
    return seen
