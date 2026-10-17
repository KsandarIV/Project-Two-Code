"""`zbone search` and `zbone links`: Zetesis (la ricerca) and the links between entries (0.1.2)."""

from typing import Dict, List, Optional, Sequence, Tuple

import typer

from zibaldone.cli.common import open_store
from zibaldone.core.areas import parse_area
from zibaldone.core.links import KIND_WIKI, LinkInfo
from zibaldone.core.search import SearchHit
from zibaldone.core.templates import Template

QUERY_HELP = 'parole (tutte devono esserci), "frase esatta", parol* per l\'inizio, -parola per escludere'
# Register with these settings, so that `zbone search casa -mare` reads -mare as a word to exclude.
SEARCH_CONTEXT = {"ignore_unknown_options": True}


def styled(text: str, highlights: Sequence[Tuple[int, int]]) -> str:
    """Text with the matched words in bold cyan (plain when the output is not a terminal)."""
    parts, last = [], 0
    for start, end in highlights:
        parts += [text[last:start], typer.style(text[start:end], fg=typer.colors.CYAN, bold=True)]
        last = end
    parts.append(text[last:])
    return "".join(parts)


def template_name(templates: Dict[str, Template], slug: Optional[str]) -> str:
    template = templates.get(slug or "")
    return template.name if template else (slug or "")


def print_hit(hit: SearchHit, templates: Dict[str, Template]) -> None:
    name = template_name(templates, hit.entry.template)
    typer.echo(f"  {hit.entry.short_id}  {hit.entry.day}  {name:<18} {styled(hit.title, hit.title_highlights)}")
    if hit.snippet:
        typer.echo(f"  {'':8}  {'':10}  {styled(hit.snippet.text, hit.snippet.highlights)}")


def search_command(
    query: Optional[List[str]] = typer.Argument(None, metavar="TESTO", help=QUERY_HELP),
    template: Optional[str] = typer.Option(None, "--template", help="solo un modello (nome tecnico)"),
    tags: List[str] = typer.Option([], "--tag", help="solo le voci con questa etichetta (si può ripetere)"),
    since: Optional[str] = typer.Option(None, help="dal giorno (AAAA-MM-GG, GG/MM/AAAA, oggi, ieri)"),
    until: Optional[str] = typer.Option(None, help="al giorno"),
    limit: int = typer.Option(20, min=1, max=500, help="quanti risultati al massimo"),
    area: Optional[str] = typer.Option(None, "--area", help="solo un'area della vita (personale, salute … svago)"),
) -> None:
    """Cerca tra le voci (Zetesis, la ricerca): parole, frasi, etichette e date."""
    with open_store() as store:
        if template:
            store.get_template(template)
        result = store.search(
            " ".join(query or []), template=template, tags=tags, since=since, until=until, limit=limit, area=parse_area(area) if area else None
        )
        templates = {item.slug: item for item in store.list_templates()}
        if result.query.unusable:
            typer.echo("Nella ricerca non c'è nessuna parola da cercare: prova con lettere o numeri.")
            return
        if not result.hits:
            typer.echo("Nessuna voce trovata.")
        else:
            searched = f" per «{result.query}»" if result.query.terms else ""
            count = "1 voce" if result.total == 1 else f"{result.total} voci"
            typer.echo(f"Zetesis · {count}{searched}\n")
            for hit in result.hits:
                print_hit(hit, templates)
            if result.total > len(result.hits):
                typer.echo(f"\nMostro {len(result.hits)} voci su {result.total}: usa --limit per vederne di più.")
        if not result.fts:
            typer.echo("\n(ricerca semplice: su questo dispositivo SQLite non ha FTS5; i risultati sono gli stessi, solo più lenti)")


def describe(templates: Dict[str, Template], template: Optional[str], day: Optional[str], entry_id: Optional[str]) -> str:
    parts = [template_name(templates, template), day or "", f"id {entry_id[:8]}" if entry_id else ""]
    return " · ".join(part for part in parts if part)


def print_outgoing(link: LinkInfo, templates: Dict[str, Template]) -> None:
    if link.resolved:
        typer.echo(f"  → {link.target_title}  ({describe(templates, link.target_template, link.target_day, link.target)}; {link.how})")
    elif link.kind == KIND_WIKI:
        typer.echo(f"  → [[{link.target_title}]]  (ancora senza voce: si collegherà da solo quando ci sarà una voce con questo titolo)")
    else:
        typer.echo(f"  → {link.target_title}  (la voce non c'è più; {link.how})")


def print_backlink(link: LinkInfo, templates: Dict[str, Template]) -> None:
    typer.echo(f"  ← {link.source_title}  ({describe(templates, link.source_template, link.source_day, link.source)}; {link.how})")


def links_command(
    reference: str = typer.Argument(..., metavar="ID", help="identificativo della voce (bastano le prime 4 lettere)"),
    mentions: bool = typer.Option(True, "--mentions/--no-mentions", help="mostra anche le voci che la nominano senza collegarla"),
) -> None:
    """I collegamenti di una voce: verso chi punta e chi la cita ("tutto su Marco")."""
    with open_store() as store:
        about = store.about(reference, mentions=20 if mentions else 0)
        templates = {item.slug: item for item in store.list_templates()}
        entry = about.entry
        typer.echo(about.title)
        typer.echo(f"  {describe(templates, entry.template, entry.day, entry.id)}\n")
        typer.echo(f"Collega ({len(about.outgoing)}):" if about.outgoing else "Non collega altre voci.")
        for link in about.outgoing:
            print_outgoing(link, templates)
        typer.echo("")
        typer.echo(f"Citata da ({len(about.backlinks)}):" if about.backlinks else "Nessuna voce la cita.")
        for link in about.backlinks:
            print_backlink(link, templates)
        if about.mentions:
            typer.echo(f"\nLa nominano senza collegamento ({len(about.mentions)}):")
            for hit in about.mentions:
                print_hit(hit, templates)
            typer.echo("  Per collegarle scrivi [[" + about.title + "]] nel testo.")


__all__ = ["SEARCH_CONTEXT", "links_command", "search_command"]
