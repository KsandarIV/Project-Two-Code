"""«La tua home» (0.3.0): the tiles of Oggi on a grid, each with a place and a size.

Pure rules over lists of `Placement`; the file in the data folder is `storage/home_log.py`.
A key is one of `TILES`, or `vista:<id>` for a saved view (`core/views.py`).
Whether the grid is 5 columns by 6 rows or the other way round is not settled: only COLS and ROWS say so.
"""

from dataclasses import dataclass, replace
from typing import Collection, Iterable, List, Optional, Tuple

COLS, ROWS = 5, 6
TILES = ("promemoria", "citazione", "aree", "abitudini", "ricorrenze", "obiettivi", "bilancio")
VIEW_PREFIX = "vista:"

# key -> (min_w, min_h, max_w, max_h, default_w, default_h); the defaults of the base tiles fill the grid exactly
_FREE = (1, 1, COLS, 3)
TILE_SIZES = {
    "promemoria": (*_FREE, 5, 1),
    "citazione": (*_FREE, 5, 1),
    "aree": (*_FREE, 5, 1),
    "abitudini": (*_FREE, 3, 1),
    "ricorrenze": (*_FREE, 2, 1),
    "obiettivi": (*_FREE, 3, 1),
    "bilancio": (*_FREE, 2, 1),
}
VIEW_SIZE = (1, 1, 5, 3, 5, 2)


class HomeError(ValueError):
    """A home action cannot run. Messages are for the user."""


@dataclass(frozen=True)
class Placement:
    key: str
    col: int  # from 0
    row: int  # from 0
    w: int
    h: int


def is_view_key(key: str) -> bool:
    return key.startswith(VIEW_PREFIX) and len(key) > len(VIEW_PREFIX)


def is_known(key: object) -> bool:
    return isinstance(key, str) and (key in TILES or is_view_key(key))


def sizes(key: str) -> Tuple[int, int, int, int, int, int]:
    return TILE_SIZES.get(key, VIEW_SIZE)


def _in_grid(p: Placement) -> bool:
    return p.col >= 0 and p.row >= 0 and p.col + p.w <= COLS and p.row + p.h <= ROWS


def _overlap(a: Placement, b: Placement) -> bool:
    return a.col < b.col + b.w and b.col < a.col + a.w and a.row < b.row + b.h and b.row < a.row + a.h


def _free(layout: Iterable[Placement], p: Placement) -> bool:
    return _in_grid(p) and not any(_overlap(p, other) for other in layout)


def first_free(layout: Iterable[Placement], w: int, h: int) -> Optional[Tuple[int, int]]:
    """The first (col, row) in reading order where a w×h tile fits."""
    taken = list(layout)
    for row in range(ROWS):
        for col in range(COLS):
            if _free(taken, Placement("", col, row, w, h)):
                return col, row
    return None


def _fit(key: str, w: int, h: int) -> Tuple[int, int]:
    min_w, min_h, max_w, max_h, _, _ = sizes(key)
    return max(min_w, min(max_w, w)), max(min_h, min(max_h, h))


def validate(layout: Iterable[Placement]) -> List[Placement]:
    """Drop unknown or repeated keys, force the size limits, drop what leaves the grid or overlaps (the first one wins). Never raises."""
    kept: List[Placement] = []
    for p in layout:
        if not isinstance(p, Placement) or not is_known(p.key) or any(k.key == p.key for k in kept):
            continue
        w, h = _fit(p.key, p.w, p.h)
        placed = replace(p, w=w, h=h)
        if _free(kept, placed):
            kept.append(placed)
    return kept


def from_list(keys: Iterable[object]) -> List[Placement]:
    """The old list layout (0.2.8) as a grid: tiles stacked in order at their default size; those that do not fit stay hidden."""
    layout: List[Placement] = []
    for key in keys:
        if not is_known(key) or any(p.key == key for p in layout):
            continue
        _, _, _, _, w, h = sizes(key)
        spot = first_free(layout, w, h)
        if spot:
            layout.append(Placement(key, spot[0], spot[1], w, h))
    return layout


def default_layout(view_ids: Collection[str] = ()) -> List[Placement]:
    """Every base tile; saved views start hidden (`hidden` lists them)."""
    return from_list(TILES)


def hidden(layout: Iterable[Placement], view_ids: Collection[str] = ()) -> List[str]:
    shown = {p.key for p in layout}
    return [key for key in (*TILES, *(VIEW_PREFIX + view for view in view_ids)) if key not in shown]


def _others(layout: Iterable[Placement], key: str) -> List[Placement]:
    return [p for p in layout if p.key != key]


def place(layout: Iterable[Placement], key: str, col: int, row: int, w: Optional[int] = None, h: Optional[int] = None) -> List[Placement]:
    """Move, resize or add a tile. The size stays as it is (or the default for a tile not there yet) unless given."""
    if not is_known(key):
        raise HomeError(f"riquadro sconosciuto: «{key}». Sono: {', '.join(TILES)} e vista:<id>")
    current = list(layout)
    old = next((p for p in current if p.key == key), None)
    min_w, min_h, max_w, max_h, def_w, def_h = sizes(key)
    w = w if w is not None else (old.w if old else def_w)
    h = h if h is not None else (old.h if old else def_h)
    if not (min_w <= w <= max_w and min_h <= h <= max_h):
        raise HomeError(f"«{key}» può essere largo da {min_w} a {max_w} e alto da {min_h} a {max_h} celle")
    placed = Placement(key, col, row, w, h)
    if not _in_grid(placed):
        raise HomeError(f"«{key}» esce dalla griglia ({COLS} colonne per {ROWS} righe)")
    rest = _others(current, key)
    clash = next((p for p in rest if _overlap(placed, p)), None)
    if clash:
        raise HomeError(f"«{key}» finirebbe sopra «{clash.key}»")
    if old:
        return [placed if p.key == key else p for p in current]
    return [*current, placed]


def remove(layout: Iterable[Placement], key: str) -> List[Placement]:
    current = list(layout)
    if not any(p.key == key for p in current):
        raise HomeError(f"«{key}» non è nella home")
    if len(current) == 1:
        raise HomeError("la home deve avere almeno un riquadro")
    return _others(current, key)


def compact(layout: Iterable[Placement]) -> List[Placement]:
    """Slide every tile up, then left, as far as it goes, in reading order (row, then column), so that order does not change."""
    result: List[Placement] = []
    for p in sorted(validate(layout), key=lambda p: (p.row, p.col)):
        moved = True
        while moved:
            moved = False
            for up, left in ((1, 0), (0, 1)):
                step = replace(p, row=p.row - up, col=p.col - left)
                if _free(result, step):
                    p, moved = step, True
        result.append(p)
    return result
