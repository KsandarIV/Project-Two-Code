"""`zbone graph`: Rizoma, the graph of the links between entries (0.1.3)."""

from pathlib import Path
from typing import List, Optional

import typer

from zibaldone.cli.common import fail, open_store
from zibaldone.core.graph import GraphFilters, graph_from_store, render_html


def write_file(path: Path, text: str) -> Path:
    path = path.expanduser()
    if not path.parent.exists():
        fail(f"la cartella {path.parent} non esiste")
    try:
        path.write_text(text, encoding="utf-8")
    except OSError as error:
        fail(f"non riesco a scrivere {path}: {error}")
    return path


def graph_command(
    html_file: Optional[Path] = typer.Option(None, "--html", help="salva il grafo come pagina HTML da aprire nel browser"),
    json_file: Optional[Path] = typer.Option(None, "--json", help="salva nodi, archi e posizioni (0..1) in JSON"),
    templates: List[str] = typer.Option([], "--template", "-t", help="solo questi modelli (si può ripetere)"),
    since: Optional[str] = typer.Option(None, help="voci dal giorno"),
    until: Optional[str] = typer.Option(None, help="voci fino al giorno"),
    tag: Optional[str] = typer.Option(None, "--tag", help="solo le voci con questa etichetta"),
    around: Optional[str] = typer.Option(None, "--around", metavar="ID", help="solo le voci vicine a questa"),
    depth: int = typer.Option(1, "--depth", min=0, max=10, help="con --around: a quanti passi di distanza"),
    tag_nodes: bool = typer.Option(False, "--tag-nodes", help="mostra anche le etichette come nodi"),
    template_nodes: bool = typer.Option(False, "--template-nodes", help="mostra anche i modelli come nodi"),
    shared_tags: bool = typer.Option(False, "--shared-tags", help="collega le voci con etichette in comune"),
    unresolved: bool = typer.Option(False, "--unresolved", help="mostra i \\[\\[titoli]] che non hanno ancora una voce"),
    isolated: bool = typer.Option(True, "--isolated/--no-isolated", help="mostra le voci senza collegamenti"),
) -> None:
    """Il grafo dei collegamenti (Rizoma): riepilogo, pagina HTML o JSON."""
    filters = GraphFilters(
        templates=tuple(templates), since=since, until=until, tag=tag, around=around, depth=depth,
        tag_nodes=tag_nodes, template_nodes=template_nodes, shared_tags=shared_tags, unresolved=unresolved, isolated=isolated,
    )
    with open_store() as store:
        for slug in templates:
            store.get_template(slug)
        graph = graph_from_store(store, filters)
    facts = graph.facts
    typer.echo(f"Rizoma · {facts.entries} voci, {facts.edges} collegamenti, {facts.components} gruppi")
    if facts.entries:
        if facts.components and facts.largest_component > 1:
            typer.echo(f"  Il gruppo più grande ha {facts.largest_component} nodi.")
        if facts.hubs:
            typer.echo("  Le più collegate: " + ", ".join(f"{label} ({degree})" for _, label, degree in facts.hubs[:5]))
        if facts.isolated:
            typer.echo(f"  Voci senza collegamenti: {len(facts.isolated)}" + ("" if isolated else " (nascoste)"))
        if facts.unresolved:
            typer.echo(f"  [[Titoli]] che aspettano ancora una voce: {facts.unresolved}")
    else:
        typer.echo("  Nessuna voce con questi filtri.")
    if html_file:
        typer.echo(f"Pagina salvata: {write_file(html_file, render_html(graph))}")
    if json_file:
        typer.echo(f"Dati salvati: {write_file(json_file, graph.to_json() + chr(10))}")


__all__ = ["graph_command"]
