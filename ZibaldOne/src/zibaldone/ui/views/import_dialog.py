"""«Importa»: libri, film, anime e giochi dai file di Goodreads, Letterboxd, MyAnimeList e Steam (0.2.5).

Four steps: choose the service, pick the file, see what would be added, confirm.
Reading and writing run in the background; only a file the user picks is read.
"""

from pathlib import Path
from typing import Any, Callable, List, Tuple

import flet as ft

from zibaldone.core import importers
from zibaldone.ui import cloud_model as cm
from zibaldone.ui import theme as T
from zibaldone.ui import widgets as W
from zibaldone.ui.context import AppContext


def read_picked(picked: Any) -> bytes:
    """The bytes of a picked file: from its path on PC and phone, from the data in the browser."""
    if getattr(picked, "path", None):
        return importers.read_path(Path(picked.path))
    if getattr(picked, "bytes", None):
        return bytes(picked.bytes)
    raise importers.ImportFileError(f"non riesco a leggere «{picked.name}» da qui")


def open_import(ctx: AppContext, after: Callable[[], Any]) -> None:
    """Step 1: which service. `after` runs once something was imported (to redraw the screen)."""

    def chosen(source: importers.Source) -> Callable[[Any], None]:
        def handler(_: Any) -> None:
            ctx.close_dialog()
            ctx.pick_files(lambda files: read(ctx, source, files, after), multiple=False)

        return handler

    rows: List[ft.Control] = [W.body("Scegli da dove vengono i dati. Si legge solo il file che scegli: ZibaldOne non entra nei tuoi account.", dim=True)]
    for source in importers.SOURCES.values():
        rows.append(
            ft.Container(
                ft.Column([W.body(f"{source.name} · {source.what}"), W.caption(source.how)], spacing=2),
                padding=ft.Padding.symmetric(horizontal=10, vertical=8),
                border=ft.Border.all(1, T.BORDER),
                border_radius=T.RADIUS_SMALL,
                on_click=chosen(source),
                ink=True,
            )
        )
    ctx.show_dialog(
        ft.AlertDialog(
            title="Importa da un file",
            content=ft.Container(ft.Column(rows, scroll=ft.ScrollMode.AUTO, spacing=8), width=440, height=420),
            actions=[W.text_button("Chiudi", ctx.close_dialog)],
        )
    )


def read(ctx: AppContext, source: importers.Source, files: List[Any], after: Callable[[], Any]) -> None:
    """Step 2 and 3: read the picked file in the background and count what would be added."""
    if not files:
        return
    picked = files[0]

    def work() -> Tuple[importers.Parsed, importers.ImportResult]:
        parsed = source.parse(read_picked(picked), getattr(picked, "name", ""))
        with ctx.store() as store:
            return parsed, importers.import_items(store, parsed.items, dry_run=True)

    def done(found: Tuple[importers.Parsed, importers.ImportResult]) -> None:
        confirm(ctx, source, found[0], found[1], after)

    ctx.run_blocking(work, done, lambda problem: ctx.toast(cm.error_text(problem), error=True))


def confirm(ctx: AppContext, source: importers.Source, parsed: importers.Parsed, preview: importers.ImportResult, after: Callable[[], Any]) -> None:
    """Step 4: what was found, and the button that writes it."""
    lines: List[ft.Control] = [W.body(f"Dal file di {source.name}: {preview.summary(dry_run=True)}")]
    notes = [*preview.problems, *parsed.problems]
    if notes:
        lines.append(W.caption(f"{len(notes)} da saltare: " + "; ".join(notes[:3]) + ("…" if len(notes) > 3 else ""), color=T.ERROR))

    def run(_: Any) -> None:
        ctx.close_dialog()

        def work() -> importers.ImportResult:
            with ctx.store() as store:
                return importers.import_items(store, parsed.items)

        def done(result: importers.ImportResult) -> None:
            ctx.toast(result.summary())
            ctx.data_changed()
            after()

        ctx.run_blocking(work, done, lambda problem: ctx.toast(cm.error_text(problem), error=True))

    actions: List[ft.Control] = [W.text_button("Annulla", ctx.close_dialog, color=T.TEXT_DIM)]
    if preview.total:
        actions.append(W.primary_button("Importa", run, icon="DOWNLOAD"))
    elif any("manca il modello" in note for note in preview.problems):
        actions.append(W.primary_button("Vai alle Scuole", lambda _: (ctx.close_dialog(), ctx.go("/scuole")), icon="SCHOOL_OUTLINED"))
    ctx.show_dialog(ft.AlertDialog(title="Importa", content=ft.Container(ft.Column(lines, spacing=8), width=420), actions=actions))
