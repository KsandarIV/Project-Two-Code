"""Drafts of entries left half-written (0.2.9): `drafts.json` in the data folder, one draft per new template and per edited entry.

Sealed secrets and media are never kept here: a draft is plain text on disk, so only the other blocks go in.
"""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from zibaldone.core.templates import Template

DRAFTS_FILE = "drafts.json"
KEPT_OUT = ("secret", "media")


def key_of(template_slug: str, entry_id: str = "") -> str:
    return f"edit:{entry_id}" if entry_id else f"new:{template_slug}"


def load_all(folder: Path) -> Dict[str, Dict[str, Any]]:
    """Every draft by key; a missing or damaged file is no drafts (the form must always open)."""
    try:
        data = json.loads((folder / DRAFTS_FILE).read_text(encoding="utf-8"))
        drafts = data.get("drafts") if isinstance(data, dict) else None
    except (OSError, ValueError):
        return {}
    return {key: draft for key, draft in (drafts or {}).items() if isinstance(draft, dict) and isinstance(draft.get("values"), dict)}


def get(folder: Path, key: str) -> Optional[Dict[str, Any]]:
    return load_all(folder).get(key)


def _write(folder: Path, drafts: Mapping[str, Any]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=".drafts-", suffix=".tmp", dir=folder)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump({"drafts": drafts}, stream, indent=2, ensure_ascii=False)
        os.replace(temporary, folder / DRAFTS_FILE)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def put(folder: Path, template: Template, values: Mapping[str, Any], day: str, area: str, entry_id: str, now: datetime) -> None:
    """Keep the draft; no value at all means there is nothing worth keeping, so an earlier draft goes."""
    kept_out = {spec.key for spec in template.blocks if spec.type in KEPT_OUT}
    plain = {key: value for key, value in values.items() if key not in kept_out}
    key = key_of(template.slug, entry_id)
    if not plain:
        discard(folder, key)
        return
    drafts = load_all(folder)
    drafts[key] = {"template": template.slug, "entry": entry_id, "day": day, "area": area, "values": plain, "saved": now.isoformat(timespec="seconds")}
    _write(folder, drafts)


def discard(folder: Path, key: str) -> None:
    drafts = load_all(folder)
    if drafts.pop(key, None) is not None:
        _write(folder, drafts)
