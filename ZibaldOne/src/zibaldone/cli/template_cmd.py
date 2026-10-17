"""`zbone template …`: create, list, show and delete templates."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import typer

from zibaldone.cli.common import ask_yes_no, open_store
from zibaldone.core.areas import area_label, parse_area
from zibaldone.core.blocks import BLOCK_TYPES
from zibaldone.core.templates import BlockSpec, Template, slugify

template_app = typer.Typer(help="Modelli: le ricette di blocchi per le tue voci.", no_args_is_help=True)


def parse_block_flag(flag: str) -> BlockSpec:
    """'titolo:text:Titolo!' -> required text block; label defaults to the key."""
    parts = flag.split(":", 2)
    if len(parts) < 2:
        raise ValueError(f"blocco '{flag}': usa chiave:tipo[:Etichetta][!]")
    key, block_type = parts[0].strip(), parts[1].strip()
    label = parts[2].strip() if len(parts) == 3 else key.replace("_", " ").capitalize()
    required = label.endswith("!") or block_type.endswith("!")
    return BlockSpec(key=key, type=block_type.rstrip("!"), label=label.rstrip("!").strip() or key, required=required)


def apply_option_flags(blocks: List[BlockSpec], flags: List[str]) -> None:
    """'voto.max=10' or 'umore.choices=["Bene","Male"]' (JSON values, plain text otherwise)."""
    by_key = {block.key: block for block in blocks}
    for flag in flags:
        target, _, raw = flag.partition("=")
        key, _, option = target.partition(".")
        if not option or key not in by_key:
            raise ValueError(f"opzione '{flag}': usa blocco.opzione=valore con un blocco esistente")
        try:
            value: Any = json.loads(raw)
        except json.JSONDecodeError:
            value = [part.strip() for part in raw.split(",")] if option == "choices" else raw
        by_key[key].options[option] = value


def ask_blocks() -> List[BlockSpec]:
    typer.echo("\nTipi di blocco:")
    names = list(BLOCK_TYPES)
    for number, name in enumerate(names, 1):
        typer.echo(f"  {number:>2}. {name:<10} {BLOCK_TYPES[name].nickname} · {BLOCK_TYPES[name].description}")
    blocks: List[BlockSpec] = []
    while True:
        label = typer.prompt("\nEtichetta del blocco (vuoto per finire)", default="", show_default=False).strip()
        if not label:
            if blocks:
                return blocks
            typer.echo("Serve almeno un blocco.")
            continue
        choice = typer.prompt("Tipo (numero o nome)", default="text").strip()
        block_type = names[int(choice) - 1] if choice.isdigit() and 1 <= int(choice) <= len(names) else choice
        if block_type not in BLOCK_TYPES:
            typer.echo(f"Tipo sconosciuto: {block_type}")
            continue
        options: Dict[str, Any] = {}
        if block_type == "choice":
            options["choices"] = [part.strip() for part in typer.prompt("Scelte separate da virgola").split(",") if part.strip()]
        elif block_type == "scale":
            options["min"] = int(typer.prompt("Minimo", default="0"))
            options["max"] = int(typer.prompt("Massimo", default="10"))
        elif block_type == "rating":
            options["max"] = int(typer.prompt("Stelle massime", default="5"))
        key = slugify(label)
        if any(block.key == key for block in blocks):
            key = f"{key}_{len(blocks) + 1}"
        spec = BlockSpec(key=key, type=block_type, label=label, required=ask_yes_no("Obbligatorio?"), options=options)
        try:
            spec.validate()
        except ValueError as error:
            typer.echo(f"Blocco non valido: {error}")
            continue
        blocks.append(spec)


@template_app.command("create")
def create_template(
    name: Optional[str] = typer.Argument(None, help="nome del modello, per esempio 'Libro'"),
    block: List[str] = typer.Option([], "--block", "-b", help="chiave:tipo[:Etichetta][!] (! = obbligatorio)"),
    option: List[str] = typer.Option([], "--option", "-o", help="blocco.opzione=valore"),
    slug: Optional[str] = typer.Option(None, help="nome tecnico (di base dal nome)"),
    description: str = typer.Option("", help="a cosa serve"),
    category: str = typer.Option("", help="per raggruppare: diario, collezioni, io, persone …"),
    area: str = typer.Option("", "--area", "-a", help="l'area della vita delle sue voci: personale, salute … svago"),
    from_file: Optional[Path] = typer.Option(None, "--from-file", help="modello in formato JSON"),
) -> None:
    """Crea un modello: con --block, da file JSON o con domande."""
    with open_store() as store:
        if from_file:
            template = Template.from_dict(json.loads(from_file.read_text(encoding="utf-8")))
        else:
            if not name:
                name = typer.prompt("Nome del modello").strip()
            blocks = [parse_block_flag(flag) for flag in block] if block else ask_blocks()
            apply_option_flags(blocks, option)
            template = Template(
                slug=slug or slugify(name), name=name, blocks=blocks, description=description, category=category,
                area=parse_area(area) if area else "",
            ).validate()
        store.save_template(template)
        typer.echo(f"Modello creato: {template.name} ({template.slug}) con {len(template.blocks)} blocchi.")
        typer.echo(f"Aggiungi una voce: zbone entry add {template.slug}")


@template_app.command("list")
def list_templates(category: Optional[str] = typer.Option(None, help="solo una categoria")) -> None:
    """Elenca i modelli installati."""
    with open_store() as store:
        templates = store.list_templates(category)
        if not templates:
            typer.echo("Nessun modello. Crea il primo con `zbone template create` o installa `zbone pack install diario`.")
            return
        width = max(len(template.slug) for template in templates)
        for template in templates:
            count = store.count_entries(template.slug)
            group = f"[{template.category}] " if template.category else ""
            area = f" · {area_label(template.area)}" if template.area else ""
            typer.echo(f"  {template.slug.ljust(width)}  {group}{template.name} · {len(template.blocks)} blocchi · {count} voci{area}")


@template_app.command("show")
def show_template(slug: str, as_json: bool = typer.Option(False, "--json", help="stampa il modello in JSON")) -> None:
    """Mostra i blocchi di un modello."""
    with open_store() as store:
        template = store.get_template(slug)
        if as_json:
            typer.echo(json.dumps(template.to_dict(), ensure_ascii=False, indent=2))
            return
        typer.echo(f"{template.name} ({template.slug})" + (f" — {template.description}" if template.description else ""))
        if template.area:
            typer.echo(f"Area: {area_label(template.area)}")
        if template.origin:
            typer.echo(f"Provenienza: {template.origin.get('pack_id', '')} {template.origin.get('pack_version', '')}".rstrip())
        for spec in template.blocks:
            mark = " *" if spec.required else ""
            options = f" {json.dumps(spec.options, ensure_ascii=False)}" if spec.options else ""
            typer.echo(f"  {spec.key:<16} {spec.type:<10} {spec.label}{mark}{options}")
        typer.echo("(* = obbligatorio)")


@template_app.command("area")
def set_template_area(
    slug: str = typer.Argument(..., metavar="MODELLO"),
    area: str = typer.Argument(..., metavar="AREA", help="personale, salute, finanze, famiglia, sociale, lavoro, studio, svago o nessuna"),
) -> None:
    """Sceglie l'area della vita delle voci di un modello."""
    with open_store() as store:
        template = store.get_template(slug)
        template.area = "" if area.strip().lower() in ("nessuna", "none", "-") else parse_area(area)
        store.save_template(template, replace=True)
        if template.area:
            typer.echo(f"Le voci di «{template.name}» ora sono nell'area {area_label(template.area)}, se non ne scelgono un'altra.")
        else:
            typer.echo(f"«{template.name}» non ha più un'area: le sue voci contano solo l'area scelta da ciascuna.")


@template_app.command("delete")
def delete_template(slug: str, yes: bool = typer.Option(False, "--yes", "-y", help="non chiedere conferma")) -> None:
    """Cancella un modello senza voci."""
    with open_store() as store:
        template = store.get_template(slug)
        if not yes and not ask_yes_no(f"Cancellare il modello '{template.name}'?"):
            raise typer.Exit()
        store.delete_template(slug)
        typer.echo(f"Modello '{template.name}' cancellato.")


@template_app.command("blocks")
def list_block_types() -> None:
    """Elenca i tipi di blocco disponibili."""
    for name, block_type in BLOCK_TYPES.items():
        options = ", ".join(block_type.options) or "nessuna"
        typer.echo(f"  {name:<10} {block_type.nickname} · {block_type.label}: {block_type.description} (opzioni: {options})")

