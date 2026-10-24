"""`zbone viste …`: Theoria (0.2.8), saved searches."""

from typing import List, Optional

import typer

from zibaldone.cli.common import fail, open_store
from zibaldone.core import views as V
from zibaldone.storage.database import StoreError

view_app = typer.Typer(help="Theoria: ricerche salvate («tutti i libri in corso») da riaprire con un tocco.", no_args_is_help=False)


def _filters(view: V.View) -> str:
    parts = [f"modello {view.template}" if view.template else "", f"area {view.area}" if view.area else "", f"testo «{view.text}»" if view.text else "", f"{view.field} = {view.value}" if view.field else ""]
    return ", ".join(part for part in parts if part) or "tutte le voci"


def _views(store) -> List[V.View]:
    if store.find_template(V.TEMPLATE) is None:
        fail(f"manca la Scuola «Theoria · Viste»: zbone pack install {V.PACK_NAME}")
    return V.load_views(store)


@view_app.callback(invoke_without_command=True)
def list_views(ctx: typer.Context) -> None:
    """Le viste salvate."""
    if ctx.invoked_subcommand is not None:
        return
    with open_store() as store:
        views = _views(store)
    if not views:
        typer.echo("Nessuna vista. Salvane una: zbone viste salva NOME --modello libro --campo stato=\"In corso\"")
        return
    for view in views:
        typer.echo(f"  {view.name} · {_filters(view)} · {view.order.lower()}")


@view_app.command("mostra")
def show(name: str = typer.Argument(..., metavar="NOME", help="anche solo le prime lettere"), limit: int = typer.Option(20, "--max", help="quante voci mostrare")) -> None:
    """Le voci di una vista."""
    try:
        with open_store() as store:
            view = V.find_view(_views(store), name)
            templates = {template.slug: template for template in store.list_templates()}
            entries = V.run_view(store, view, limit=limit)
    except (V.ViewError, StoreError) as error:
        fail(str(error))
    typer.echo(f"{view.name} · {_filters(view)}\n")
    if not entries:
        typer.echo("Nessuna voce.")
    for entry in entries:
        template = templates.get(entry.template)
        typer.echo(f"  {entry.short_id}  {entry.day}  {template.name if template else entry.template:<18} {entry.title(template) if template else entry.id}")


@view_app.command("salva")
def save(
    name: str = typer.Argument(..., metavar="NOME"),
    template: str = typer.Option("", "--modello", help="il nome tecnico del modello, per esempio libro"),
    area: str = typer.Option("", "--area"),
    text: str = typer.Option("", "--testo", help="come nella ricerca"),
    field: Optional[str] = typer.Option(None, "--campo", metavar="CAMPO=VALORE", help="un filtro su un blocco, per esempio stato=\"In corso\""),
    order: str = typer.Option(V.RECENT, "--ordine", help=f"{V.RECENT} oppure {V.BY_TITLE}"),
) -> None:
    """Salva una vista."""
    key, _, value = (field or "").partition("=")
    if field is not None and not value:
        fail("il filtro si scrive CAMPO=VALORE, per esempio stato=\"In corso\"")
    try:
        with open_store() as store:
            _views(store)
            view = V.save_view(store, name, template=template, area=area, text=text, field=key, value=value, order=order)
    except (V.ViewError, StoreError) as error:
        fail(str(error))
    typer.echo(f"Vista «{view.name}» salvata: {_filters(view)}.")


@view_app.command("togli")
def remove(name: str = typer.Argument(..., metavar="NOME")) -> None:
    """Toglie una vista (le voci restano dove sono)."""
    try:
        with open_store() as store:
            view = V.find_view(_views(store), name)
            V.delete_view(store, view.id)
    except (V.ViewError, StoreError) as error:
        fail(str(error))
    typer.echo(f"Vista «{view.name}» tolta.")
