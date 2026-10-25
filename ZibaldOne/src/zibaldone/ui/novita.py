"""The release notes shown in «Novità»: one JSON file per version under `assets/novita/`, written with each release.

File: `{"versione": "0.2.9", "data": "AAAA-MM-GG", "titolo": "...", "voci": [{"tipo": "nuovo"|"migliorato"|"corretto", "testo": "..."}]}`.
The last version the person opened is kept in the `ui` settings, so the button can tell when something is new.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from zibaldone.ui import services
from zibaldone.ui.widgets import ASSETS_DIR

NOTES_DIR = "novita"
SEEN_KEY = "novita_viste"
KINDS = {"nuovo": "Nuovo", "migliorato": "Migliorato", "corretto": "Corretto"}


@dataclass(frozen=True)
class Release:
    version: str
    date: str
    title: str
    items: Tuple[Tuple[str, str], ...]  # (kind, text)


def _key(version: str) -> Tuple[int, ...]:
    return tuple(int(part) if part.isdigit() else 0 for part in version.split("."))


def load_releases(assets: Optional[Path] = None) -> List[Release]:
    """Every readable file, the newest version first; a broken file is skipped."""
    folder = (assets or ASSETS_DIR) / NOTES_DIR
    found: List[Release] = []
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            items = tuple((str(item["tipo"]), str(item["testo"])) for item in data["voci"])
            found.append(Release(str(data["versione"]), str(data.get("data", "")), str(data.get("titolo", "")), items))
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return sorted(found, key=lambda release: _key(release.version), reverse=True)


def has_unseen(folder: Path, releases: List[Release]) -> bool:
    return bool(releases) and services.ui_settings(folder).get(SEEN_KEY, "") != releases[0].version


def mark_seen(folder: Path, releases: List[Release]) -> None:
    if releases:
        services.save_ui_settings(folder, **{SEEN_KEY: releases[0].version})
