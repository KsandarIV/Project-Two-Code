"""`zbone importa FONTE FILE`: libri, film, anime e giochi dai file di altri servizi (0.2.5)."""

from pathlib import Path

import typer

from zibaldone.cli.common import fail, open_store
from zibaldone.core import importers


def import_command(
    source: str = typer.Argument(..., metavar="FONTE", help="goodreads, letterboxd, myanimelist o steam"),
    file: Path = typer.Argument(..., metavar="FILE", help="il file esportato dal servizio"),
    dry_run: bool = typer.Option(False, "--prova", help="mostra cosa verrebbe aggiunto, senza scrivere"),
) -> None:
    """Importa libri, film, anime e giochi da un file esportato da Goodreads, Letterboxd, MyAnimeList o Steam."""
    try:
        parsed = importers.get_source(source).parse(importers.read_path(file), file.name)
    except importers.ImportFileError as error:
        fail(str(error))
    with open_store() as store:
        result = importers.import_items(store, parsed.items, dry_run=dry_run)
    typer.echo(result.summary(dry_run))
    problems = [*parsed.problems, *result.problems]
    for problem in problems[:10]:
        typer.echo(f"  - {problem}")
    if problems:
        typer.echo(f"{len(problems)} righe non importate.")
        if not result.total:
            raise typer.Exit(code=1)
