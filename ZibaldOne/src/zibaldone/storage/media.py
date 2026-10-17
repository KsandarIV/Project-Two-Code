"""The attached files (0.2.4): photos, video, audio and documents, in `<data folder>/media/`.

A file is stored once under the SHA-256 of its content plus its extension
(`3f2a….jpg`), so the same photo attached twice takes the space of one. An
entry's media block only names the file (`{"file", "name", "size"}`, see
`core/blocks.py`). Files that no entry names any more are removed by
`remove_unused`, but only after an hour, so a file picked in a form that is
still open is never lost. The backups keep their own copies
(`storage/backups.py`).
"""

import hashlib
import os
import re
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set

from zibaldone.core.blocks import MEDIA_FILE, media_kind

MEDIA_DIR = "media"
MAX_MEDIA_BYTES = 100 * 1024 * 1024  # one file; it is read whole to seal it in the backups
UNUSED_GRACE_SECONDS = 3600
CHUNK = 1024 * 1024


class MediaError(Exception):
    """An attachment cannot be added or read. Messages are for the user."""


@dataclass(frozen=True)
class Attachment:
    file: str
    name: str
    size: int

    @property
    def kind(self) -> str:
        return media_kind(self.name)

    def to_value(self) -> Dict[str, Any]:
        return {"file": self.file, "name": self.name, "size": self.size}


def media_dir(folder: Path) -> Path:
    return folder / MEDIA_DIR


def path_of(folder: Path, file: str) -> Path:
    if not MEDIA_FILE.match(file or ""):
        raise MediaError("allegato non valido")
    return media_dir(folder) / file


def _extension(name: str) -> str:
    extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    return f".{extension}" if re.fullmatch(r"[a-z0-9]{1,8}", extension) else ""


def size_label(size: int) -> str:
    for unit, step in (("GB", 1024**3), ("MB", 1024**2), ("KB", 1024)):
        if size >= step:
            return f"{size / step:.1f} {unit}".replace(".", ",")
    return f"{size} byte"


def _write_new(folder: Path, file: str, data: bytes) -> None:
    target = path_of(folder, file)
    if target.exists():
        os.utime(target)  # attached again: not an old unused file any more
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".zbtmp-{secrets.token_hex(4)}")
    try:
        with open(temporary, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()


def add_bytes(folder: Path, name: str, data: bytes) -> Attachment:
    """Keep `data` in the media folder; the same content is stored only once."""
    name = os.path.basename((name or "").replace("\\", "/")).strip() or "allegato"
    if len(data) > MAX_MEDIA_BYTES:
        raise MediaError(f"«{name}» è troppo grande: al massimo {size_label(MAX_MEDIA_BYTES)} per file")
    if not data:
        raise MediaError(f"«{name}» è vuoto")
    file = hashlib.sha256(data).hexdigest() + _extension(name)
    _write_new(folder, file, data)
    return Attachment(file=file, name=name[:200], size=len(data))


def add_file(folder: Path, source: Path) -> Attachment:
    """Copy a file from anywhere into the media folder."""
    source = Path(source)
    try:
        if not source.is_file():
            raise MediaError(f"«{source}» non è un file")
        if source.stat().st_size > MAX_MEDIA_BYTES:
            raise MediaError(f"«{source.name}» è troppo grande: al massimo {size_label(MAX_MEDIA_BYTES)} per file")
        data = source.read_bytes()
    except OSError as error:
        raise MediaError(f"non riesco a leggere «{source}»: {error.strerror or error}") from None
    return add_bytes(folder, source.name, data)


def read(folder: Path, file: str) -> bytes:
    try:
        return path_of(folder, file).read_bytes()
    except OSError:
        raise MediaError("il file di questo allegato non c'è più su questo dispositivo: ripristina un backup") from None


def stored_files(folder: Path) -> List[str]:
    directory = media_dir(folder)
    if not directory.is_dir():
        return []
    return sorted(path.name for path in directory.iterdir() if path.is_file() and MEDIA_FILE.match(path.name))


def attachments_of(template: Any, values: Dict[str, Any]) -> List[Attachment]:
    return [
        Attachment(item["file"], item["name"], item["size"])
        for spec in template.blocks
        if spec.type == "media"
        for item in values.get(spec.key) or []
    ]


def referenced_files(store: Any) -> Set[str]:
    """Every file named by an entry."""
    templates = {template.slug: template for template in store.list_templates() if any(spec.type == "media" for spec in template.blocks)}
    found: Set[str] = set()
    for entry in store.list_entries():
        template = templates.get(entry.template)
        if template is not None:
            found.update(item.file for item in attachments_of(template, entry.values))
    return found


def remove_unused(folder: Path, referenced: Iterable[str], now: float = 0.0) -> List[str]:
    """Delete the files no entry names, if older than the grace period. Returns their names."""
    keep = set(referenced)
    limit = (now or time.time()) - UNUSED_GRACE_SECONDS
    removed = []
    for file in stored_files(folder):
        path = path_of(folder, file)
        try:
            if file not in keep and path.stat().st_mtime < limit:
                path.unlink()
                removed.append(file)
        except OSError:
            continue
    return removed
