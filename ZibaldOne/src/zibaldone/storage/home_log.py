"""The layout of Oggi lives in `home.json` in the data folder, like the reminder log."""

import json
import os
import tempfile
from pathlib import Path
from typing import Collection, List, Optional

from zibaldone.core.home import DEFAULT_LAYOUT, clean_layout

HOME_FILE = "home.json"


def home_path(folder: Path) -> Path:
    return folder / HOME_FILE


def load_layout(folder: Path, view_ids: Optional[Collection[str]] = None) -> List[str]:
    """The saved tiles; unknown keys, and views missing from `view_ids` when given, are dropped. No file, a broken one or nothing left = the default."""
    try:
        data = json.loads(home_path(folder).read_text(encoding="utf-8"))
        tiles = data.get("tiles") if isinstance(data, dict) else None
    except (OSError, ValueError):
        return list(DEFAULT_LAYOUT)  # the home must always open: a damaged file is just not used
    return clean_layout(tiles if isinstance(tiles, list) else [], view_ids)


def save_layout(folder: Path, tiles: List[str]) -> List[str]:
    """Write the cleaned layout atomically (temporary file, then rename) and return it."""
    kept = clean_layout(tiles)
    folder.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=".home-", suffix=".tmp", dir=folder)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump({"tiles": kept}, stream, indent=2, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, home_path(folder))
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
    return kept


def reset_layout(folder: Path) -> None:
    home_path(folder).unlink(missing_ok=True)
