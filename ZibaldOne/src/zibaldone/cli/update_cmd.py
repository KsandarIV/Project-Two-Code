"""`zbone update`: is there a newer ZibaldOne on GitHub?"""

from typing import Optional

import typer

from zibaldone import __version__
from zibaldone.cli.common import ensure_consent, fail
from zibaldone.cloud import updates
from zibaldone.cloud.http import CloudError
from zibaldone.storage.paths import data_dir
from zibaldone.storage.settings import SettingsError


def check_updates(
    auto: Optional[bool] = typer.Option(None, "--auto/--no-auto", help="accende o spegne il controllo automatico dell'app (una volta al giorno)"),
) -> None:
    """Controlla se è uscita una versione nuova di ZibaldOne."""
    ensure_consent()
    folder = data_dir()
    if auto is not None:
        try:
            updates.set_auto_check(folder, auto)
        except (SettingsError, OSError) as error:
            fail(str(error))
        typer.echo("Controllo automatico acceso: l'app guarda una volta al giorno." if auto else "Controllo automatico spento: controlla tu con `zbone update`.")
        return
    try:
        release = updates.check_now(folder)
    except (CloudError, SettingsError, OSError) as error:
        fail(str(error))
    if release is None:
        typer.echo(f"Hai la versione più recente ({__version__}).")
        return
    typer.echo(f"È uscita ZibaldOne {release.version} (tu hai la {__version__}).")
    typer.echo(f"  Novità e download: {release.page_url}")
    if release.apk_url:
        typer.echo(f"  APK per Android:   {release.apk_url}")
    typer.echo("  Sul PC, dalla cartella del progetto: git pull, poi pip install -e .")
