"""«La tua home» (0.2.8): which tiles Oggi shows and in which order.

Pure rules over a list of keys; the file in the data folder is `storage/home_log.py`.
A key is one of `TILES`, or `vista:<id>` for a saved view (`core/views.py`).
"""

from typing import Collection, Iterable, List, Optional

TILES = ("promemoria", "citazione", "stoa", "aree", "abitudini", "ricorrenze", "obiettivi", "bilancio")
FIXED = ("promemoria", "citazione", "stoa", "aree")  # on Oggi they cannot be taken away (0.3.2); only Kosmesis can switch them off
DEFAULT_LAYOUT = list(TILES)
VIEW_PREFIX = "vista:"


class HomeError(ValueError):
    """A home action cannot run. Messages are for the user."""


def is_view_key(key: str) -> bool:
    return key.startswith(VIEW_PREFIX) and len(key) > len(VIEW_PREFIX)


def clean_layout(keys: Iterable[object], view_ids: Optional[Collection[str]] = None) -> List[str]:
    """The known keys in order, each once; with `view_ids`, a view that is not there any more goes too. Nothing left = the default layout."""
    kept: List[str] = []
    for key in keys:
        if not isinstance(key, str) or key in kept:
            continue
        if key in TILES or (is_view_key(key) and (view_ids is None or key[len(VIEW_PREFIX) :] in view_ids)):
            kept.append(key)
    return kept or list(DEFAULT_LAYOUT)


def _check(key: str) -> None:
    if key not in TILES and not is_view_key(key):
        raise HomeError(f"riquadro sconosciuto: «{key}». Sono: {', '.join(TILES)} e vista:<id>")


def add_tile(layout: List[str], key: str) -> List[str]:
    _check(key)
    return layout if key in layout else [*layout, key]


def remove_tile(layout: List[str], key: str) -> List[str]:
    if key not in layout:
        raise HomeError(f"«{key}» non è nella home")
    if len(layout) == 1:
        raise HomeError("la home deve avere almeno un riquadro")
    return [item for item in layout if item != key]


def move_tile(layout: List[str], key: str, position: int) -> List[str]:
    """Put the tile at `position` (1 = first); past the end means last."""
    if key not in layout:
        raise HomeError(f"«{key}» non è nella home")
    rest = [item for item in layout if item != key]
    at = max(0, min(position - 1, len(rest)))
    return [*rest[:at], key, *rest[at:]]
