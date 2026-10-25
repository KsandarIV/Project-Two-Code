"""The layout of Oggi lives in `home.json` in the data folder, like the reminder log.

Format 2 (0.3.0): `{"versione": 2, "riquadri": [{"key", "col", "row", "w", "h"}, …]}`.
The 0.2.8 file, `{"tiles": [keys…]}`, is still read and becomes a grid.
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Collection, List, Optional

from zibaldone.core import home as H
from zibaldone.core.home import Placement

HOME_FILE = "home.json"
VERSION = 2


def home_path(folder: Path) -> Path:
    return folder / HOME_FILE


def _int(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else -1


def _from_dicts(rows: List[Any]) -> List[Placement]:
    return [Placement(row.get("key"), _int(row.get("col")), _int(row.get("row")), _int(row.get("w")), _int(row.get("h"))) for row in rows if isinstance(row, dict)]


def load_layout(folder: Path, view_ids: Optional[Collection[str]] = None) -> List[Placement]:
    """The saved grid, checked; with `view_ids`, a view that is not there any more goes too. No file, a broken one or nothing left = the default."""
    try:
        data = json.loads(home_path(folder).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return H.default_layout()  # the home must always open: a damaged file is just not used
    layout: List[Placement] = []
    if isinstance(data, dict) and isinstance(data.get("riquadri"), list):
        layout = _from_dicts(data["riquadri"])
    elif isinstance(data, dict) and isinstance(data.get("tiles"), list):
        layout = H.from_list(data["tiles"])  # views missing from `view_ids` go below
    if view_ids is not None:
        layout = [p for p in layout if not H.is_view_key(p.key) or p.key[len(H.VIEW_PREFIX) :] in view_ids]
    return H.validate(layout) or H.default_layout()


def save_layout(folder: Path, layout: List[Placement]) -> List[Placement]:
    """Check the grid, write it atomically (temporary file, then rename) and return it."""
    kept = H.validate(layout) or H.default_layout()
    folder.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=".home-", suffix=".tmp", dir=folder)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump({"versione": VERSION, "riquadri": [{"key": p.key, "col": p.col, "row": p.row, "w": p.w, "h": p.h} for p in kept]}, stream, indent=2, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, home_path(folder))
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
    return kept


def reset_layout(folder: Path) -> None:
    home_path(folder).unlink(missing_ok=True)
