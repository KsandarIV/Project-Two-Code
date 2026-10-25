"""Backup files (.zbbackup): save one snapshot to a file, and bring a file back, either added to the list or as the data itself.

Used by Mnemosyne (Impostazioni) and by the first start («Ho già un backup»). The file work is `storage/bundle`.
"""

from pathlib import Path
from typing import Any, Callable, Optional

import flet as ft

from zibaldone.storage import bundle
from zibaldone.ui import cloud_model as cm
from zibaldone.ui import theme as T
from zibaldone.ui import widgets as W
from zibaldone.ui.context import AppContext

EXPORT_DIR = "exports"
SKIPPED_KEY = "backup_trovato_scartato"


def export_snapshot(ctx: AppContext, snapshot_id: str) -> None:
    """Write the snapshot to `exports` in the data folder, say where, and on a phone open the share sheet to put it anywhere."""
    folder = ctx.folder

    def work() -> Path:
        return bundle.export_bundle(folder, snapshot_id, folder / EXPORT_DIR)

    def done(path: Path) -> None:
        _exported(ctx, path)
        ctx.open_file(path) if _on_phone(ctx) else None

    ctx.run_blocking(work, done, lambda problem: ctx.toast(f"Backup non esportato: {cm.error_text(problem)}", error=True))


def _on_phone(ctx: AppContext) -> bool:
    platform = getattr(ctx.page, "platform", None)
    return bool(platform is not None and platform.is_mobile())


def _exported(ctx: AppContext, path: Path) -> None:
    ctx.toast("File di backup creato.")
    ctx.show_dialog(
        ft.AlertDialog(
            title="File di backup creato",
            content=ft.Column(
                [
                    W.body("Il file è qui:"),
                    W.panel(W.body(str(path), selectable=True, size=13), padding=10, bgcolor=T.BG),
                    W.caption("Copialo dove vuoi: un'altra cartella, una chiavetta, il cloud. Per riaverlo, in Mnemosyne scegli «Importa da un file». Sul telefono si apre anche il menu per condividerlo."),
                ],
                spacing=10,
                tight=True,
            ),
            actions=[W.primary_button("Va bene", ctx.close_dialog)],
        )
    )


def import_file(ctx: AppContext, on_done: Optional[Callable[[], Any]] = None) -> None:
    """Pick a backup file, read what it says about itself, then offer «add to the list» or «restore my data»."""

    def picked(files: list) -> None:
        if not files:
            return
        raw = getattr(files[0], "path", None)
        if not raw:
            ctx.toast("Il selettore non ha dato il percorso del file: riprova da una cartella del telefono.", error=True)
            return
        path = Path(raw)
        ctx.run_blocking(lambda: bundle.inspect_bundle(path), lambda info: _offer(ctx, path, info, on_done), lambda problem: ctx.toast(cm.error_text(problem), error=True))

    ctx.pick_files(picked, multiple=False)


def _offer(ctx: AppContext, path: Path, info: Any, on_done: Optional[Callable[[], Any]]) -> None:
    if not info.ok:
        ctx.toast("; ".join(info.problems).capitalize() + ".", error=True)
        return
    when = info.created_at.astimezone().strftime("%d/%m/%Y alle %H:%M") if info.created_at else "data sconosciuta"
    passphrase = W.text_input("", label="Passphrase dei backup", password=True, can_reveal_password=True, visible=info.encrypted)
    recovery = W.text_input("", label="oppure il codice di recupero", visible=info.encrypted)
    error = W.error_text()

    def finish(text: str) -> None:
        ctx.close_dialog()
        ctx.toast(text)
        ctx.data_changed()
        if on_done is not None:
            on_done()
        else:
            ctx.refresh()

    def fail(problem: Exception) -> None:
        error.value = cm.error_text(problem)
        error.visible = True
        ctx.update(error)

    def add(_: Any) -> None:
        ctx.run_blocking(lambda: bundle.import_bundle(ctx.folder, path), lambda _result: finish("Aggiunto alle istantanee. Da lì puoi riportare i dati a quel momento."), fail)

    def restore(_: Any) -> None:
        pass_value, code = (passphrase.value or "").strip() or None, (recovery.value or "").strip() or None
        ctx.run_blocking(lambda: bundle.restore_bundle(ctx.folder, path, passphrase=pass_value, recovery_code=code), lambda _result: finish("Dati riportati al backup. Prima ne ho salvata un'istantanea per tornare indietro."), fail)

    lines = [
        W.body(f"Backup del {when}" + (f", fatto con ZibaldOne {info.app_version}" if info.app_version else "") + (", cifrato." if info.encrypted else ".")),
        W.caption("«Ripristina i dati» sostituisce quelli di ora con questo backup (ne salvo prima una copia per tornare indietro). «Aggiungi alle istantanee» non cambia nulla."),
        passphrase,
        recovery,
        error,
    ]
    ctx.show_dialog(
        ft.AlertDialog(
            title="Backup trovato",
            content=ft.Container(ft.Column(lines, spacing=10, tight=True), width=440),
            actions=[W.text_button("Annulla", ctx.close_dialog, color=T.TEXT), W.secondary_button("Aggiungi alle istantanee", add), W.primary_button("Ripristina i dati", restore, icon="SETTINGS_BACKUP_RESTORE")],
        )
    )


def found_backup_panel(ctx: AppContext, on_done: Callable[[], Any]) -> Optional[ft.Control]:
    """On a new installation: a backup file found in the usual folders, with the way to bring it back; None when there is none (or it was set aside)."""
    if ctx.memory.get(SKIPPED_KEY):
        return None
    try:
        candidate = bundle.first_run_candidate(ctx.folder)
    except OSError:
        return None
    if candidate is None:
        return None
    when = candidate.created_at.astimezone().strftime("%d/%m/%Y alle %H:%M") if candidate.created_at else "data sconosciuta"

    def skip(_: Any) -> None:
        ctx.memory[SKIPPED_KEY] = True
        ctx.refresh()

    return W.panel(
        ft.Column(
            [
                W.body("Ho trovato un tuo backup di ZibaldOne.", weight=ft.FontWeight.W_600),
                W.caption(f"Del {when}, in {candidate.path.parent}"),
                ft.Row([W.text_button("Parto da zero", skip, color=T.TEXT_DIM), W.primary_button("Riporta i miei dati", lambda _: _offer(ctx, candidate.path, candidate, on_done), icon="SETTINGS_BACKUP_RESTORE")], alignment=ft.MainAxisAlignment.END, wrap=True, spacing=8),
            ],
            spacing=6,
        ),
        border_color=W.fade(T.ACCENT, 0.5),
    )
