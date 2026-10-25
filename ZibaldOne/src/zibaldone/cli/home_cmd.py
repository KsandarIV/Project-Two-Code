"""`zbone home …`: «La tua home» (0.3.0), the tiles of Oggi on a grid.

On the command line columns and rows count from 1, as people do; `core/home.py` counts from 0.
"""

from typing import Callable, List, Optional

import typer

from zibaldone.cli.common import fail, open_store
from zibaldone.core import home as Home
from zibaldone.core import views as V
from zibaldone.core.home import Placement
from zibaldone.storage import home_log
from zibaldone.storage.database import StoreError
from zibaldone.storage.paths import data_dir

home_app = typer.Typer(help=f"La tua home: i riquadri di Oggi su una griglia di {Home.COLS} colonne per {Home.ROWS} righe. Colonne e righe si contano da 1.", no_args_is_help=False)

CELL = 6


def _views() -> list:
    with open_store() as store:
        return V.load_views(store)


def _key(text: str, views: list) -> str:
    """`vista:NOME` (name or first letters) becomes `vista:<id>`; every other key is used as typed."""
    if not text.startswith(Home.VIEW_PREFIX):
        return text
    try:
        return Home.VIEW_PREFIX + V.find_view(views, text[len(Home.VIEW_PREFIX) :]).id
    except V.ViewError as error:
        fail(str(error))
        raise


def _view_name(key: str, views: list) -> str:
    view = next((view for view in views if view.id == key[len(Home.VIEW_PREFIX) :]), None)
    return f"vista:{view.name}" if view else key


def _show(layout: List[Placement], views: list) -> None:
    label = {}
    for p in layout:
        label[p.key] = f"v{sum(1 for key in label if Home.is_view_key(key)) + 1}" if Home.is_view_key(p.key) else p.key[: CELL - 1]
    typer.echo("   " + "".join(f"{col:<{CELL}}" for col in range(1, Home.COLS + 1)).rstrip())
    for row in range(Home.ROWS):
        cells = [next((label[p.key] for p in layout if p.col <= col < p.col + p.w and p.row <= row < p.row + p.h), "·") for col in range(Home.COLS)]
        typer.echo(f"{row + 1:>2} " + "".join(f"{cell:<{CELL}}" for cell in cells).rstrip())
    for p in layout:
        if Home.is_view_key(p.key):
            typer.echo(f"{label[p.key]} = {_view_name(p.key, views)}")
    off = Home.hidden(layout, {view.id for view in views})
    if off:
        typer.echo(f"Nascosti: {', '.join(_view_name(key, views) if Home.is_view_key(key) else key for key in off)}")


def _load(views: list) -> List[Placement]:
    return home_log.load_layout(data_dir(), {view.id for view in views})


@home_app.callback(invoke_without_command=True)
def show(ctx: typer.Context) -> None:
    """La griglia di Oggi e i riquadri nascosti."""
    if ctx.invoked_subcommand is not None:
        return
    views = _views()
    _show(_load(views), views)


def _change(action: Callable[[List[Placement], list], List[Placement]]) -> None:
    views = _views()
    try:
        layout = home_log.save_layout(data_dir(), action(_load(views), views))
    except (Home.HomeError, StoreError, OSError) as error:
        fail(str(error))
        raise
    _show(layout, views)


def _find(layout: List[Placement], key: str) -> Placement:
    found = next((p for p in layout if p.key == key), None)
    if found is None:
        raise Home.HomeError(f"«{key}» non è nella home")
    return found


@home_app.command("aggiungi")
def add(
    key: str = typer.Argument(..., metavar="CHIAVE", help="un riquadro (promemoria, citazione, aree, abitudini, ricorrenze, obiettivi, bilancio) o vista:NOME"),
    col: Optional[int] = typer.Argument(None, metavar="COL"),
    row: Optional[int] = typer.Argument(None, metavar="RIGA"),
) -> None:
    """Mostra un riquadro, nel primo posto libero o dove dici."""

    def action(layout: List[Placement], views: list) -> List[Placement]:
        name = _key(key, views)
        if any(p.key == name for p in layout):
            return layout
        if col is None or row is None:
            _, _, _, _, w, h = Home.sizes(name)
            spot = Home.first_free(layout, w, h)
            if spot is None:
                raise Home.HomeError("non c'è posto: togli o rimpicciolisci un riquadro")
            return Home.place(layout, name, *spot)
        return Home.place(layout, name, col - 1, row - 1)

    _change(action)


@home_app.command("togli")
def remove(key: str = typer.Argument(..., metavar="CHIAVE")) -> None:
    """Nasconde un riquadro."""
    _change(lambda layout, views: Home.remove(layout, _key(key, views)))


@home_app.command("sposta")
def move(key: str = typer.Argument(..., metavar="CHIAVE"), col: int = typer.Argument(..., metavar="COL"), row: int = typer.Argument(..., metavar="RIGA")) -> None:
    """Sposta un riquadro, che tiene la sua misura."""

    def action(layout: List[Placement], views: list) -> List[Placement]:
        name = _key(key, views)
        _find(layout, name)
        return Home.place(layout, name, col - 1, row - 1)

    _change(action)


@home_app.command("ridimensiona")
def resize(key: str = typer.Argument(..., metavar="CHIAVE"), width: int = typer.Argument(..., metavar="LARG"), height: int = typer.Argument(..., metavar="ALT")) -> None:
    """Cambia larghezza e altezza (in celle) di un riquadro, che resta dov'è."""

    def action(layout: List[Placement], views: list) -> List[Placement]:
        name = _key(key, views)
        here = _find(layout, name)
        return Home.place(layout, name, here.col, here.row, width, height)

    _change(action)


@home_app.command("ordina")
def tidy() -> None:
    """Porta i riquadri in alto a sinistra, senza cambiare l'ordine."""
    _change(lambda layout, views: Home.compact(layout))


@home_app.command("ripristina")
def reset() -> None:
    """Rimette la home di base."""
    home_log.reset_layout(data_dir())
    typer.echo("Home ripristinata.")
