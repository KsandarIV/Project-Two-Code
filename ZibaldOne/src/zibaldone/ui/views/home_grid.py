"""Oggi as a grid (0.3.0): each tile sits at a cell with a size; «Modifica home» moves and resizes them with buttons.

The rules (limits, overlaps, the grid size) are `core/home`; this module only draws and calls it.
"""

from typing import Any, Callable, Dict, List, Optional, Sequence

import flet as ft

from zibaldone.core import home
from zibaldone.core.home import HomeError, Placement
from zibaldone.storage import home_log
from zibaldone.ui import theme as T
from zibaldone.ui import widgets as W
from zibaldone.ui.context import AppContext

GAP = 8
ROW_HEIGHT_PHONE = 128
ROW_HEIGHT_WIDE = 148
RAIL_WIDTH = 96  # the navigation rail takes this much on a wide layout
EDIT_KEY = "home_modifica"

LABELS: Dict[str, str] = {
    "promemoria": "Promemoria",
    "citazione": "Pensiero del giorno",
    "aree": "Le otto aree",
    "abitudini": "Abitudini di oggi",
    "ricorrenze": "Ricorrenze",
    "obiettivi": "Obiettivi",
    "bilancio": "Bilancio",
}


def label_of(key: str, view_names: Dict[str, str]) -> str:
    if home.is_view_key(key):
        return f"Vista: {view_names.get(key[len(home.VIEW_PREFIX):], 'non più disponibile')}"
    return LABELS.get(key, key)


def editing(ctx: AppContext) -> bool:
    return bool(ctx.memory.get(EDIT_KEY))


def set_editing(ctx: AppContext, value: bool) -> None:
    ctx.memory[EDIT_KEY] = value


def grid_width(ctx: AppContext) -> float:
    """The width the grid can use: the page minus the rail, the share the content takes and its side padding."""
    page = float(getattr(ctx.page, "width", None) or 400)
    if not ctx.wide:
        return max(page - 32, 200)
    columns = 8 if page >= 1400 else 10 if page >= 1200 else 11 if page >= 992 else 12
    return max((page - RAIL_WIDTH) * columns / 12 - 56, 320)


def _rows_shown(layout: Sequence[Placement], filled: Sequence[str]) -> List[int]:
    """The grid rows that hold at least one tile with something to show; the others are left out so no gap stays."""
    return sorted({row for p in layout if p.key in filled for row in range(p.row, p.row + p.h)})


def grid(ctx: AppContext, layout: Sequence[Placement], blocks: Dict[str, Optional[ft.Control]], force_rows: bool = False) -> ft.Control:
    """The tiles as positioned boxes. A tile whose block is None leaves its cells empty (and an empty row is dropped)."""
    filled = [p.key for p in layout if blocks.get(p.key) is not None]
    rows = _rows_shown(layout, filled if not force_rows else [p.key for p in layout])
    if not rows:
        return ft.Container(height=0)
    cell_w = (grid_width(ctx) - GAP * (home.COLS - 1)) / home.COLS
    row_h = ROW_HEIGHT_WIDE if ctx.wide else ROW_HEIGHT_PHONE
    index = {row: n for n, row in enumerate(rows)}
    boxes: List[ft.Control] = []
    for p in layout:
        block = blocks.get(p.key)
        if block is None:
            continue
        spanned = [index[row] for row in range(p.row, p.row + p.h) if row in index]
        boxes.append(
            ft.Container(
                block,
                left=p.col * (cell_w + GAP),
                top=spanned[0] * (row_h + GAP),
                width=p.w * cell_w + (p.w - 1) * GAP,
                height=len(spanned) * row_h + (len(spanned) - 1) * GAP,
                clip_behavior=ft.ClipBehavior.HARD_EDGE,
            )
        )
    return ft.Stack(boxes, width=home.COLS * cell_w + (home.COLS - 1) * GAP, height=len(rows) * row_h + (len(rows) - 1) * GAP)


def fit(block: ft.Control) -> ft.Control:
    """A tile's content in its cells: it scrolls when it does not fit, so nothing is cut off without a way to read it."""
    return ft.Column([block], scroll=ft.ScrollMode.AUTO, expand=True, spacing=0)


# * — edit mode —


def _view_names(ctx: AppContext) -> Dict[str, str]:
    from zibaldone.core import views as V

    with ctx.store() as store:
        return {item.id: item.name for item in V.load_views(store)} if store.find_template(V.TEMPLATE) is not None else {}


def _apply(ctx: AppContext, change: Callable[[], List[Placement]]) -> None:
    try:
        home_log.save_layout(ctx.folder, change())
    except HomeError as problem:
        ctx.toast(str(problem), error=True)
        return
    ctx.refresh()


def _tile_editor(ctx: AppContext, layout: List[Placement], p: Placement, names: Dict[str, str]) -> ft.Control:
    def move(dc: int, dr: int) -> Callable[[Any], None]:
        return lambda _: _apply(ctx, lambda: home.place(layout, p.key, p.col + dc, p.row + dr))

    def size(dw: int, dh: int) -> Callable[[Any], None]:
        return lambda _: _apply(ctx, lambda: home.place(layout, p.key, p.col, p.row, p.w + dw, p.h + dh))

    buttons = [
        W.icon_button("ARROW_BACK", move(-1, 0), "A sinistra", size=18),
        W.icon_button("ARROW_FORWARD", move(1, 0), "A destra", size=18),
        W.icon_button("ARROW_UPWARD", move(0, -1), "Su", size=18),
        W.icon_button("ARROW_DOWNWARD", move(0, 1), "Giù", size=18),
        W.icon_button("UNFOLD_LESS", size(-1, 0), "Meno largo", size=18),
        W.icon_button("UNFOLD_MORE", size(1, 0), "Più largo", size=18),
        W.icon_button("REMOVE", size(0, -1), "Meno alto", size=18),
        W.icon_button("ADD", size(0, 1), "Più alto", size=18),
        W.icon_button("VISIBILITY_OFF_OUTLINED", lambda _: _apply(ctx, lambda: home.remove(layout, p.key)), "Nascondi", size=18),
    ]
    return W.panel(
        ft.Column([W.caption(f"{label_of(p.key, names)} · {p.w}×{p.h}"), ft.Row(buttons, wrap=True, spacing=0, run_spacing=0)], spacing=2, scroll=ft.ScrollMode.AUTO),
        padding=6,
        border_color=W.fade(T.ACCENT, 0.5),
    )


def edit_view(ctx: AppContext) -> ft.Control:
    """The grid with the buttons on every tile, then the hidden tiles with «Aggiungi»."""
    names = _view_names(ctx)
    layout = home_log.load_layout(ctx.folder, set(names))
    blocks: Dict[str, Optional[ft.Control]] = {p.key: _tile_editor(ctx, layout, p, names) for p in layout}

    def add(key: str) -> Callable[[Any], None]:
        def run(_: Any) -> None:
            _, _, _, _, w, h = home.sizes(key)
            spot = home.first_free(layout, w, h)
            if spot is None:
                ctx.toast("Non c'è posto per un riquadro in più: nascondine uno o rimpiccioliscilo.", error=True)
                return
            _apply(ctx, lambda: home.place(layout, key, spot[0], spot[1]))

        return run

    left = [key for key in home.hidden(layout, set(names))]
    controls: List[ft.Control] = [
        W.panel(
            ft.Column(
                [
                    W.body("Modifica la home", weight=ft.FontWeight.W_600),
                    W.caption("Ogni riquadro ha le frecce per spostarlo e i pulsanti per cambiarne la larghezza e l'altezza. Se un cambio non è possibile, te lo dico e non cambia nulla."),
                    ft.Row(
                        [
                            W.secondary_button("Ordina", lambda _: _apply(ctx, lambda: home.compact(layout)), icon="VERTICAL_ALIGN_TOP"),
                            W.secondary_button("Ripristina", lambda _: ctx.confirm("Ripristinare la home?", "I riquadri tornano come all'inizio.", "Ripristina", lambda: (home_log.reset_layout(ctx.folder), ctx.refresh()), danger=False), icon="RESTART_ALT"),
                            W.primary_button("Fine", lambda _: (set_editing(ctx, False), ctx.refresh()), icon="CHECK"),
                        ],
                        wrap=True,
                        spacing=8,
                    ),
                ],
                spacing=8,
            ),
            border_color=W.fade(T.ACCENT, 0.5),
        ),
        grid(ctx, layout, blocks, force_rows=True),
    ]
    if left:
        controls.append(W.section_label("Nascosti"))
        controls.append(W.panel(ft.Column([ft.Row([W.body(label_of(key, names), dim=True, expand=True), W.text_button("Aggiungi", add(key), icon="ADD")]) for key in left], spacing=2)))
    return ft.Column(controls, spacing=12)
