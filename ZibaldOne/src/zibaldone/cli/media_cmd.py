"""`zbone allegati …`: photos, video, audio and documents attached to entries (0.2.4)."""

import shutil
from pathlib import Path
from typing import List, Optional

import typer

from zibaldone.cli.common import fail, open_store
from zibaldone.core.templates import BlockSpec, Template
from zibaldone.storage import media
from zibaldone.storage.database import Store
from zibaldone.storage.paths import data_dir

media_app = typer.Typer(help="Mimesis: foto, video, audio e documenti allegati alle voci.", no_args_is_help=False)


@media_app.callback(invoke_without_command=True)
def status(ctx: typer.Context) -> None:
    """Quanti allegati ci sono e quanto spazio occupano."""
    if ctx.invoked_subcommand is not None:
        return
    folder = data_dir()
    with open_store() as store:
        named = media.referenced_files(store)
    stored = media.stored_files(folder)
    size = sum(media.path_of(folder, file).stat().st_size for file in stored)
    typer.echo(f"Allegati: {len(named)} file, {media.size_label(size)} in {media.media_dir(folder)}")
    missing = named - set(stored)
    if missing:
        typer.echo(f"{len(missing)} allegati mancano su questo dispositivo: ripristina un backup (zbone backup restore).")


def _media_block(template: Template, key: Optional[str]) -> BlockSpec:
    specs = [spec for spec in template.blocks if spec.type == "media"]
    if not specs:
        fail(f"il modello «{template.name}» non ha un blocco Allegati: aggiungilo nell'editor dei modelli dell'app (Forme)")
    if key is None:
        return specs[0]
    found = next((spec for spec in specs if spec.key == key), None)
    if found is None:
        fail(f"«{key}» non è un blocco allegati di «{template.name}» ({', '.join(spec.key for spec in specs)})")
    return found


def _attachments(store: Store, reference: str) -> tuple:
    entry = store.get_entry(reference)
    template = store.get_template(entry.template)
    return entry, template, media.attachments_of(template, entry.values)


def _pick(items: List[media.Attachment], number: int) -> media.Attachment:
    if not 1 <= number <= len(items):
        fail(f"non c'è l'allegato {number}: vedi zbone allegati mostra")
    return items[number - 1]


@media_app.command("aggiungi")
def add(
    reference: str = typer.Argument(..., metavar="VOCE"),
    files: List[Path] = typer.Argument(..., metavar="FILE..."),
    block: Optional[str] = typer.Option(None, "--blocco", "-b", help="il blocco allegati, se la voce ne ha più di uno"),
) -> None:
    """Allega uno o più file a una voce (al massimo 100 MB l'uno)."""
    folder = data_dir()
    with open_store() as store:
        entry = store.get_entry(reference)
        template = store.get_template(entry.template)
        spec = _media_block(template, block)
        current = list(entry.values.get(spec.key) or [])
        try:
            added = [media.add_file(folder, path) for path in files]
        except media.MediaError as error:
            fail(str(error))
        store.update_entry(entry.id, {spec.key: current + [item.to_value() for item in added]})
    typer.echo(f"Allegati a «{entry.title(template)}»: {', '.join(item.name for item in added)}")


@media_app.command("mostra")
def show(reference: str = typer.Argument(..., metavar="VOCE")) -> None:
    """Gli allegati di una voce, numerati, con il file sul disco."""
    folder = data_dir()
    with open_store() as store:
        entry, template, items = _attachments(store, reference)
    typer.echo(f"{entry.title(template)} · {len(items)} allegati")
    for number, item in enumerate(items, 1):
        path = media.path_of(folder, item.file)
        where = str(path) if path.exists() else "manca su questo dispositivo"
        typer.echo(f"  {number}. {item.name} · {item.kind} · {media.size_label(item.size)} · {where}")


@media_app.command("togli")
def remove(reference: str = typer.Argument(..., metavar="VOCE"), number: int = typer.Argument(..., metavar="NUMERO")) -> None:
    """Toglie un allegato dalla voce (i backup lo conservano finché non scadono)."""
    with open_store() as store:
        entry, template, items = _attachments(store, reference)
        gone = _pick(items, number)
        changes = {
            spec.key: [value for value in entry.values.get(spec.key) or [] if value["file"] != gone.file] or None
            for spec in template.blocks
            if spec.type == "media" and spec.key in entry.values
        }
        store.update_entry(entry.id, changes)
    typer.echo(f"Tolto «{gone.name}».")


@media_app.command("salva")
def save(
    reference: str = typer.Argument(..., metavar="VOCE"),
    number: Optional[int] = typer.Argument(None, metavar="[NUMERO]"),
    target: Path = typer.Option(Path("."), "--in", help="la cartella dove copiarli"),
) -> None:
    """Copia gli allegati di una voce (o solo uno) in una cartella, con il loro nome."""
    folder = data_dir()
    with open_store() as store:
        _, _, items = _attachments(store, reference)
    chosen = [_pick(items, number)] if number is not None else items
    target.mkdir(parents=True, exist_ok=True)
    for item in chosen:
        source = media.path_of(folder, item.file)
        if not source.exists():
            fail(f"«{item.name}» manca su questo dispositivo: ripristina un backup")
        destination = _free_name(target / item.name)
        shutil.copyfile(source, destination)
        typer.echo(f"Salvato {destination}")


def _free_name(path: Path) -> Path:
    """`foto.jpg`, then `foto (2).jpg`: never overwrite."""
    candidate, number = path, 2
    while candidate.exists():
        candidate = path.with_name(f"{path.stem} ({number}){path.suffix}")
        number += 1
    return candidate

