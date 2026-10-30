"""The folder of backup files the user can see (0.3.3): where each file goes, what is kept, what is left alone.

Inside the folder the user chose, the app keeps its own scheme:

    backup/giornalieri  settimanali  mensili  annuali  manuali
    importati            copies of backup files brought in from outside
    Gestione manuale     the files that were not made by the app, set aside when the app takes over the folder
    Storico              (only when the user asks) what the rotation would have deleted

The app writes, rotates and moves only inside these folders and only `.zbbackup` files. Anything else is not touched.
Files outside the scheme are still listed («Altri») when the user keeps managing them.
"""

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

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


@dataclass(frozen=True)
class FolderFile:
    path: Path
    kind: str  # a TIER_DIRS key, "importati", "gestione", "storico" or "altri"


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


def export_snapshots(folder: Path, target: Path, mode: str) -> List[Path]:
    """Write the backup files the visible folder has not had yet; returns the new ones.

    «Gestisco io»: the newest snapshot, flat in the folder (the user's way, as before 0.3.3).
    «Gestisce l'app» and «Misto»: every manual, daily, weekly, monthly or yearly snapshot, in its own subfolder.
    """
    snapshots = [info for info in backups.list_snapshots(folder) if not info.problem]
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


def rotate(target: Path, keep_history: bool = False) -> List[Path]:
    """In each rotating subfolder keep the newest few; the rest is deleted, or moved to «Storico» when asked. Returns what left."""
    gone: List[Path] = []
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
    return gone


def keep_imported_copy(target: Path, source: Path) -> Optional[Path]:
    """A copy of a backup file brought in from outside, in «importati»; the original stays where it is."""
    if source.suffix != BUNDLE_SUFFIX or not source.is_file():
        return None
    destination = target / IMPORTED / source.name
    if destination.exists() or target in source.parents:
        return None
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return destination


def list_files(target: Path) -> List[FolderFile]:
    """Every `.zbbackup` under the folder, in whatever subfolder, told apart by where it is. Never raises."""
    found: List[FolderFile] = []
    try:
        candidates = sorted(target.rglob(f"*{BUNDLE_SUFFIX}"))
    except OSError:
        return found
    by_dir: Dict[str, str] = {name: reason for reason, name in TIER_DIRS.items()}
    for path in candidates:
        parts = path.relative_to(target).parts
        if parts[0] == ROOT and len(parts) == 3 and parts[1] in by_dir:
            kind = by_dir[parts[1]]
        elif parts[0] == IMPORTED:
            kind = "importati"
        elif parts[0] == SET_ASIDE:
            kind = "gestione"
        elif parts[0] == HISTORY:
            kind = "storico"
        else:
            kind = "altri"
        found.append(FolderFile(path, kind))
    return found


def take_over(target: Path) -> List[Path]:
    """The app starts managing the folder: the files that are not its own go, as they are, to «Gestione manuale».

    Nothing is deleted or renamed; a name already taken gets a number. Returns the new places.
    """
    moved: List[Path] = []
    for item in list_files(target):
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


def move_scheme(old: Path, new: Path) -> List[Path]:
    """The folder changes and the user wants the old files along: only the app's own subfolders move, merged into the new place."""
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
