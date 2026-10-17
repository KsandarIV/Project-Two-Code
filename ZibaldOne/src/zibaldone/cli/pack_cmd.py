"""`zbone pack …`: built-in packs, sharing templates with other people."""

from pathlib import Path
from typing import List, Optional

import typer

from zibaldone.cli.common import ask_yes_no, fail, open_store
from zibaldone.core.packs import (
    PACK_SUFFIX,
    Pack,
    apply_install,
    build_pack,
    builtin_packs,
    find_builtin_pack,
    plan_install,
    read_pack_file,
    write_pack_file,
)
from zibaldone.core.templates import slugify

pack_app = typer.Typer(help="Pacchetti di modelli: quelli pronti dell'app e quelli da condividere.", no_args_is_help=True)

ACTION_LABELS = {
    "new": "nuovo",
    "update": "aggiornato",
    "same": "già presente, salto",
    "copy": "installato come copia",
}


def load_pack(source: str) -> Pack:
    """A built-in pack name ('diario') or a path to a .zbpack.json file."""
    pack = find_builtin_pack(source)
    if pack:
        return pack
    path = Path(source)
    if path.suffix == ".json" or path.exists():
        return read_pack_file(path)
    names = ", ".join(item.short_name for item in builtin_packs())
    fail(f"'{source}' non è un pacchetto integrato ({names}) né un file {PACK_SUFFIX}")
    raise AssertionError  # unreachable: fail() exits


def print_pack(pack: Pack) -> None:
    typer.echo(f"{pack.name} {pack.version} ({pack.id})" + (f" di {pack.author}" if pack.author else ""))
    if pack.description:
        typer.echo(f"  {pack.description}")
    if pack.license:
        typer.echo(f"  Licenza: {pack.license}")
    typer.echo(f"  Blocchi usati: {', '.join(pack.required_blocks)}")
    typer.echo(f"  Modelli ({len(pack.templates)}):")
    for template in pack.templates:
        typer.echo(f"    {template.slug:<16} {template.name} · {len(template.blocks)} blocchi")


@pack_app.command("list")
def list_packs() -> None:
    """Elenca i pacchetti pronti e dice se sono installati."""
    with open_store() as store:
        installed = {template.origin.get("pack_id") for template in store.list_templates()}
        for pack in builtin_packs():
            mark = "installato" if pack.id in installed else "da installare"
            typer.echo(f"  {pack.short_name:<12} {pack.name} · {len(pack.templates)} modelli · {mark}")
            typer.echo(f"  {'':<12} {pack.description}")
        typer.echo("\nInstalla con: zbone pack install <nome>  (anche un file .zbpack.json)")


@pack_app.command("show")
def show_pack(source: str = typer.Argument(..., metavar="PACCHETTO", help="nome integrato o file .zbpack.json")) -> None:
    """Mostra il contenuto di un pacchetto senza installarlo."""
    try:
        print_pack(load_pack(source))
    except ValueError as error:
        fail(str(error))


@pack_app.command("install")
def install_pack(
    source: str = typer.Argument(..., metavar="PACCHETTO", help="nome integrato o file .zbpack.json"),
    yes: bool = typer.Option(False, "--yes", "-y", help="non chiedere conferma"),
) -> None:
    """Installa un pacchetto: prima mostra cosa cambierà."""
    with open_store() as store:
        pack = load_pack(source)
        plan = plan_install(pack, store)
        print_pack(pack)
        typer.echo("\nCosa succede:")
        for step in plan.steps:
            target = f" come '{step.target_slug}'" if step.target_slug != step.template.slug else ""
            reason = f" ({step.reason})" if step.reason and step.action == "copy" else ""
            typer.echo(f"  {step.template.name:<28} {ACTION_LABELS[step.action]}{target}{reason}")
        if all(step.action == "same" for step in plan.steps):
            typer.echo("\nNiente da fare: il pacchetto è già installato.")
            return
        typer.echo("Il pacchetto contiene solo modelli: nessun dato personale, nessun codice.")
        if not yes and not ask_yes_no("Installo?"):
            raise typer.Exit()
        installed = apply_install(plan, store)
        typer.echo(f"Installati {len(installed)} modelli. Vedi: zbone template list")


@pack_app.command("import")
def import_pack(
    path: Path = typer.Argument(..., metavar="FILE", help="file .zbpack.json ricevuto da qualcuno"),
    yes: bool = typer.Option(False, "--yes", "-y", help="non chiedere conferma"),
) -> None:
    """Importa un pacchetto da file (come install)."""
    install_pack(str(path), yes)


@pack_app.command("export")
def export_pack(
    slugs: List[str] = typer.Argument(..., metavar="MODELLI", help="nomi tecnici dei modelli da condividere"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="file di destinazione"),
    name: Optional[str] = typer.Option(None, help="nome del pacchetto"),
    author: str = typer.Option("", help="il tuo nome o nickname"),
    description: str = typer.Option("", help="a cosa serve"),
    version: str = typer.Option("1.0.0", help="versione X.Y.Z del pacchetto"),
    license_name: str = typer.Option("CC-BY-4.0", "--license", help="licenza (CC-BY-4.0, CC0-1.0 …)"),
) -> None:
    """Esporta dei modelli in un file da condividere: solo la struttura, nessuna voce."""
    with open_store() as store:
        templates = [store.get_template(slug) for slug in slugs]
        pack_name = name or (templates[0].name if len(templates) == 1 else "I miei modelli")
        pack_id = f"{slugify(author) if author else 'utente'}.{slugify(pack_name)}".replace("_", "-")
        pack = build_pack(templates, pack_id, pack_name, version, author, license_name, description)
        path = write_pack_file(pack, output or Path(f"{slugify(pack_name)}{PACK_SUFFIX}"))
        typer.echo(f"Pacchetto salvato in {path}")
        typer.echo("Contiene solo i modelli: nessuna delle tue voci è stata esportata.")
