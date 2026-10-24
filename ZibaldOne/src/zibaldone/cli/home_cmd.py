"""`zbone home …`: «La tua home» (0.2.8), the tiles of Oggi."""

import typer

from zibaldone.cli.common import fail, open_store
from zibaldone.core import home as Home
from zibaldone.core import views as V
from zibaldone.storage import home_log
from zibaldone.storage.database import StoreError
from zibaldone.storage.paths import data_dir

home_app = typer.Typer(help="La tua home: quali riquadri mostra Oggi e in che ordine.", no_args_is_help=False)


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


def _name(key: str, views: list) -> str:
    if not Home.is_view_key(key):
        return key
    view = next((view for view in views if view.id == key[len(Home.VIEW_PREFIX) :]), None)
    return f"vista:{view.name}" if view else key


def _show(layout: list, views: list) -> None:
    for number, key in enumerate(layout, 1):
        typer.echo(f"  {number}. {_name(key, views)}")
    hidden = [tile for tile in Home.TILES if tile not in layout]
    if hidden:
        typer.echo(f"Nascosti: {', '.join(hidden)}")


def _load(views: list) -> list:
    return home_log.load_layout(data_dir(), {view.id for view in views})


@home_app.callback(invoke_without_command=True)
def show(ctx: typer.Context) -> None:
    """I riquadri di Oggi, nell'ordine in cui compaiono."""
    if ctx.invoked_subcommand is not None:
        return
    views = _views()
    _show(_load(views), views)


def _change(action) -> None:
    views = _views()
    try:
        layout = action(_load(views), views)
        home_log.save_layout(data_dir(), layout)
    except (Home.HomeError, StoreError, OSError) as error:
        fail(str(error))
    _show(layout, views)


@home_app.command("aggiungi")
def add(key: str = typer.Argument(..., metavar="CHIAVE", help="un riquadro (promemoria, citazione, aree, abitudini, ricorrenze, obiettivi, bilancio) o vista:NOME")) -> None:
    """Mostra un riquadro in fondo alla home."""
    _change(lambda layout, views: Home.add_tile(layout, _key(key, views)))


@home_app.command("togli")
def remove(key: str = typer.Argument(..., metavar="CHIAVE")) -> None:
    """Nasconde un riquadro."""
    _change(lambda layout, views: Home.remove_tile(layout, _key(key, views)))


@home_app.command("sposta")
def move(key: str = typer.Argument(..., metavar="CHIAVE"), position: int = typer.Argument(1, metavar="POSIZIONE", help="1 = in cima")) -> None:
    """Sposta un riquadro (di base in cima)."""
    _change(lambda layout, views: Home.move_tile(layout, _key(key, views), position))


@home_app.command("ripristina")
def reset() -> None:
    """Rimette la home di base."""
    home_log.reset_layout(data_dir())
    typer.echo("Home ripristinata.")
