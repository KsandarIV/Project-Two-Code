"""`zbone entry …`: add, list, show, edit and delete entries."""

from typing import Any, Dict, List, Optional

import typer

from zibaldone.cli.common import ask_yes_no, open_store
from zibaldone.core.blocks import parse_day
from zibaldone.core.templates import BlockSpec, Entry, Template
from zibaldone.storage.database import Store, StoreError

entry_app = typer.Typer(help="Voci: i modelli compilati, il cuore del tuo zibaldone.", no_args_is_help=True)

HINTS = {
    "rating": "numero di stelle",
    "tags": "separate da virgola",
    "date": "AAAA-MM-GG, GG/MM/AAAA, oggi o ieri",
    "checklist": "voci separate da ; e [x] per quelle fatte",
    "progress": "per esempio 'in corso 150/320' o 'completato'",
    "longtext": "\\n per andare a capo",
    "link": "titoli o identificativi separati da virgola",
}


def resolve_links(store: Store, spec: BlockSpec, raw: str) -> List[str]:
    """Turn titles or short ids into full entry ids."""
    wanted_template = spec.options.get("template")
    candidates = store.list_entries(template=wanted_template) if wanted_template else store.list_entries()
    templates = {template.slug: template for template in store.list_templates()}
    resolved: List[str] = []
    for part in [item.strip() for item in raw.split(",") if item.strip()]:
        by_id = [entry for entry in candidates if entry.id.startswith(part.lower())] if len(part) >= 4 else []
        by_title = [entry for entry in candidates if entry.title(templates[entry.template]).lower() == part.lower()]
        matches = by_title or by_id
        if len(matches) != 1:
            raise ValueError(f"{spec.label}: '{part}' " + ("non trovato" if not matches else "è ambiguo"))
        resolved.append(matches[0].id)
    return resolved


def parse_value(store: Store, spec: BlockSpec, raw: str) -> Any:
    if spec.type == "link":
        return spec.block_type.normalize(resolve_links(store, spec, raw), spec.options)
    return spec.block_type.parse(raw, spec.options)


def parse_set_flags(store: Store, template: Template, flags: List[str]) -> Dict[str, Any]:
    values: Dict[str, Any] = {}
    for flag in flags:
        key, sep, raw = flag.partition("=")
        if not sep:
            raise ValueError(f"'{flag}': usa blocco=valore")
        spec = template.block(key.strip())
        try:
            values[spec.key] = None if raw == "" else parse_value(store, spec, raw)
        except ValueError as error:
            raise ValueError(f"{spec.label}: {error}") from None
    return values


def ask_values(store: Store, template: Template, current: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Ask every block in the terminal; empty answers keep the current value or skip."""
    values: Dict[str, Any] = {}
    typer.echo(f"{template.name}: rispondi a ogni blocco, invio per saltare.")
    for spec in template.blocks:
        hint = HINTS.get(spec.type, "")
        if spec.type == "choice":
            hint = " / ".join(f"{number}={choice}" for number, choice in enumerate(spec.options["choices"], 1))
        if spec.type == "scale":
            low, high = spec.block_type.bounds(spec.options)
            hint = f"da {low} a {high}"
        shown = ""
        if current and spec.key in current:
            shown = f" [ora: {spec.block_type.to_text(current[spec.key], spec.options)}]"
        prompt = f"{spec.label}{' *' if spec.required else ''}{f' ({hint})' if hint else ''}{shown}"
        while True:
            raw = typer.prompt(prompt, default="", show_default=False).strip()
            if not raw:
                if spec.required and not (current and spec.key in current):
                    typer.echo("  questo blocco è obbligatorio")
                    continue
                break
            try:
                values[spec.key] = parse_value(store, spec, raw)
                break
            except ValueError as error:
                typer.echo(f"  {error}")
    return values


def print_entry(entry: Entry, template: Template) -> None:
    typer.echo(f"{entry.title(template)}")
    typer.echo(f"  {template.name} · {entry.day} · id {entry.short_id}")
    for spec in template.blocks:
        if spec.key not in entry.values:
            continue
        text = spec.block_type.to_text(entry.values[spec.key], spec.options)
        if "\n" in text:
            typer.echo(f"  {spec.label}:")
            for line in text.splitlines():
                typer.echo(f"    {line}")
        else:
            typer.echo(f"  {spec.label}: {text}")


@entry_app.command("add")
def add_entry(
    template_slug: str = typer.Argument(..., metavar="MODELLO", help="nome tecnico del modello"),
    set_values: List[str] = typer.Option([], "--set", "-s", help="blocco=valore (senza --set fa le domande)"),
    day: Optional[str] = typer.Option(None, "--day", "-d", help="il giorno della voce (di base oggi)"),
) -> None:
    """Aggiunge una voce a un modello."""
    with open_store() as store:
        template = store.get_template(template_slug)
        values = parse_set_flags(store, template, set_values) if set_values else ask_values(store, template)
        entry = store.add_entry(template.slug, values, day)
        typer.echo(f"Voce salvata: {entry.title(template)} (id {entry.short_id})")


@entry_app.command("list")
def list_entries(
    template_slug: Optional[str] = typer.Option(None, "--template", "-t", help="solo un modello"),
    day: Optional[str] = typer.Option(None, "--day", "-d", help="solo un giorno"),
    since: Optional[str] = typer.Option(None, help="dal giorno"),
    until: Optional[str] = typer.Option(None, help="al giorno"),
    limit: int = typer.Option(30, help="quante voci al massimo"),
) -> None:
    """Elenca le voci, dalla più recente."""
    with open_store() as store:
        if day:
            since = until = parse_day(day)
        entries = store.list_entries(template_slug, since, until, limit)
        if not entries:
            typer.echo("Nessuna voce.")
            return
        templates = {template.slug: template for template in store.list_templates()}
        for entry in entries:
            template = templates[entry.template]
            typer.echo(f"  {entry.short_id}  {entry.day}  {template.name:<18} {entry.title(template)}")


@entry_app.command("show")
def show_entry(reference: str = typer.Argument(..., metavar="ID")) -> None:
    """Mostra una voce."""
    with open_store() as store:
        entry = store.get_entry(reference)
        print_entry(entry, store.get_template(entry.template))


@entry_app.command("edit")
def edit_entry(
    reference: str = typer.Argument(..., metavar="ID"),
    set_values: List[str] = typer.Option([], "--set", "-s", help="blocco=valore; blocco= svuota il blocco"),
    day: Optional[str] = typer.Option(None, "--day", "-d", help="sposta la voce a un altro giorno"),
) -> None:
    """Modifica una voce."""
    with open_store() as store:
        entry = store.get_entry(reference)
        template = store.get_template(entry.template)
        if set_values:
            values = parse_set_flags(store, template, set_values)
        elif day:
            values = {}
        else:
            values = ask_values(store, template, entry.values)
        entry = store.update_entry(entry.id, values, day)
        typer.echo(f"Voce aggiornata: {entry.title(template)} (id {entry.short_id})")


@entry_app.command("delete")
def delete_entry(
    reference: str = typer.Argument(..., metavar="ID"),
    yes: bool = typer.Option(False, "--yes", "-y", help="non chiedere conferma"),
) -> None:
    """Cancella una voce."""
    with open_store() as store:
        entry = store.get_entry(reference)
        template = store.get_template(entry.template)
        if not yes and not ask_yes_no(f"Cancellare '{entry.title(template)}' del {entry.day}?"):
            raise typer.Exit()
        store.delete_entry(entry.id)
        typer.echo("Voce cancellata.")


__all__ = ["entry_app", "StoreError"]
