"""First run: privacy consent (Parresia), Google sign-in when required, the diary suggestion."""

from typing import Any, Dict, List

import flet as ft

from zibaldone.core.brand import APP_MOTTO, APP_NAME, APP_TAGLINE, NOMENCLATURE, mascot_for
from zibaldone.core.packs import BASE_PACKS, builtin_packs, install_base_packs
from zibaldone.core.privacy import NOTICE_VERSION, notice_text
from zibaldone.storage import backup_folder as bf
from zibaldone.storage.database import StoreError
from zibaldone.storage.settings import SettingsError, consent_status, record_consent
from zibaldone.ui import services
from zibaldone.ui.cloud_model import app_hint
from zibaldone.ui import theme as T
from zibaldone.ui import widgets as W
from zibaldone.ui.context import AppContext
from zibaldone.ui.navigation import Route
from zibaldone.ui.views import backup_file


def _brand() -> ft.Control:
    zibby = mascot_for("app")
    return ft.Row(
        [
            W.mascot_avatar(zibby, 44),
            ft.Column([ft.Text(APP_NAME, size=28, weight=ft.FontWeight.W_700, color=T.TEXT), W.caption(APP_TAGLINE)], spacing=0, expand=True),
        ],
        spacing=14,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


def consent(ctx: AppContext, route: Route) -> ft.Control:
    privacy = NOMENCLATURE["privacy"]
    try:
        previous = consent_status(ctx.folder)
    except SettingsError:
        previous = {}
    changed = previous.get("accepted") is True and previous.get("notice_version") != NOTICE_VERSION
    refusal = W.panel(
        ft.Column(
            [
                W.body(
                    "Va bene così: le tue voci restano dove sono, e ZibaldOne non salva nulla di nuovo senza il tuo sì."
                    if changed
                    else "Va bene così: ZibaldOne non ha salvato nulla e non lo farà senza il tuo sì."
                ),
                W.body("Puoi rileggere con calma e decidere quando vuoi: questa pagina resta qui.", dim=True),
            ],
            spacing=6,
        ),
        border_color=W.fade(T.ACCENT_2, 0.5),
    )
    refusal.visible = False

    def accept(_: Any) -> None:
        try:
            record_consent(ctx.folder, accepted=True, notice_version=NOTICE_VERSION)
        except OSError as problem:
            ctx.toast(f"Non riesco a scrivere nella cartella dati: {problem}", error=True)
            return
        ctx.advance()

    def refuse(_: Any) -> None:
        refusal.visible = True
        ctx.update(refusal)

    title = "L'informativa è cambiata" if changed else "Prima di iniziare"
    intro = (
        "Da quando l'hai letta è cambiato qualcosa che ti riguarda: rileggila con calma, le tue voci sono al loro posto."
        if changed
        else f"{privacy.source}. Ecco, in chiaro, cosa succede ai tuoi dati."
    )
    return W.screen(
        [
            _brand(),
            W.title_with_nickname(title, privacy.name, size=22),
            W.body(intro, dim=True),
            W.panel(W.body(app_hint(notice_text(ctx.folder)), selectable=True)),
            refusal,
            ft.Row([W.secondary_button("Non ora", refuse), W.primary_button("Ho capito, continuiamo" if changed else "Ho capito, iniziamo", accept, icon="CHECK")], alignment=ft.MainAxisAlignment.END, wrap=True, spacing=8),
        ],
        ctx.wide,
    )


def _restored(ctx: AppContext) -> None:
    """The data came back from a backup: no account is asked for now, nor the base packs (they came with the data)."""
    services.skip_login(ctx.folder)
    services.save_ui_settings(ctx.folder, diario_suggested=True)
    ctx.go("/oggi")


def _found_backup(ctx: AppContext) -> List[ft.Control]:
    panel = backup_file.found_backup_panel(ctx, lambda: _restored(ctx))
    return [panel] if panel is not None else []


def sign_in(ctx: AppContext, route: Route) -> ft.Control:
    from zibaldone.ui.views.cloud import google_sign_in

    cloud = NOMENCLATURE["cloud"]

    def without_account(_: Any) -> None:
        try:
            services.skip_login(ctx.folder)
        except OSError as problem:
            ctx.toast(f"Non riesco a salvare la scelta: {problem}", error=True)
            return
        ctx.advance()

    why = ft.ExpansionTile(
        title=ft.Text("A che cosa serve l'accesso?", size=14, color=T.TEXT),
        controls=[
            ft.Container(
                ft.Column(
                    [
                        W.body("L'accesso riconosce te e, se vuoi, permette di tenere una copia cifrata su Google Drive.", size=13),
                        W.body("Google vede solo la tua email e il tuo nome.", size=13),
                        W.body("Drive è facoltativo: se entri, scegli dopo se usarlo.", size=13),
                        W.body("Senza account tutto resta su questo dispositivo. Puoi entrare più tardi dalle Nuvole, in Impostazioni.", size=13),
                    ],
                    spacing=6,
                ),
                padding=ft.Padding.only(left=16, right=16, bottom=12),
            )
        ],
    )
    return W.screen(
        [
            _brand(),
            *_found_backup(ctx),
            W.title_with_nickname("Entra con Google, se vuoi", cloud.name, size=22),
            W.panel(
                ft.Column(
                    [
                        W.body("Puoi entrare con il tuo account Google oppure continuare senza account: ZibaldOne funziona allo stesso modo."),
                        W.body("Entrare apre il browser: scegli l'account e torna qui. I tuoi pensieri restano su questo dispositivo.", dim=True),
                        why,
                    ],
                    spacing=8,
                )
            ),
            ft.Row([W.text_button("Ho già un backup", lambda _: backup_file.import_file(ctx, lambda: _restored(ctx)), icon="SETTINGS_BACKUP_RESTORE")], alignment=ft.MainAxisAlignment.END),
            ft.Row(
                [
                    W.secondary_button("Continua senza account", without_account),
                    W.primary_button("Entra con Google", lambda _: google_sign_in(ctx, lambda _status: ctx.advance()), icon="LOGIN"),
                ],
                alignment=ft.MainAxisAlignment.END,
                wrap=True,
                spacing=8,
            ),
        ],
        ctx.wide,
    )


def copies(ctx: AppContext, route: Route) -> ft.Control:
    """Right after the first sign-in: where the backups go, like the terminal asks."""
    from zibaldone.ui.views.cloud import use_google

    api = services.account_api()
    status, _ = services.account_status(ctx.folder)
    cloud = NOMENCLATURE["cloud"]
    email = getattr(status, "email", "") or ""

    def local(_: Any) -> None:
        if api is None:
            ctx.advance()
            return
        ctx.run_blocking(
            lambda: api.choose_mode(ctx.folder, "local"),
            lambda _status: (ctx.toast("Va bene: solo su questo dispositivo. Puoi cambiare idea nelle Nuvole."), ctx.advance()),
        )

    def google(_: Any) -> None:
        use_google(ctx, ctx.advance)

    def option(icon: str, title: str, text: str, on_click: Any, color: str) -> ft.Control:
        return W.panel(
            ft.Row(
                [
                    ft.Container(ft.Icon(W.icon_of(icon), color=color, size=24), width=44, height=44, bgcolor=W.fade(color, 0.14), border_radius=T.RADIUS_SMALL, alignment=ft.Alignment.CENTER),
                    ft.Column([W.body(title, size=16, weight=ft.FontWeight.W_600), W.body(text, dim=True, size=13)], spacing=2, expand=True),
                    ft.Icon(ft.Icons.CHEVRON_RIGHT, color=T.TEXT_DIM),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            on_click=on_click,
        )

    return W.screen(
        [
            _brand(),
            W.title_with_nickname("Dove vuoi tenere i backup?", cloud.name, size=22),
            W.body(f"Sei entrato come {email}. Le istantanee di Mnemosyne stanno sempre su questo dispositivo; puoi tenerne anche una copia fuori." if email else "Le istantanee di Mnemosyne stanno sempre su questo dispositivo; puoi tenerne anche una copia fuori.", dim=True),
            option("PHONE_ANDROID", "Solo su questo dispositivo", "Puoi cambiare idea quando vuoi, nelle Nuvole.", local, T.ACCENT),
            option("CLOUD_OUTLINED", "Anche sul mio Google Drive", "Cifrate, nello spazio nascosto dell'app: non vedi e non tocchi gli altri tuoi file.", google, T.ACCENT_2),
            W.caption("Le copie fuori partono quando attivi la cifratura dei backup: nessun dato esce dal dispositivo in chiaro."),
        ],
        ctx.wide,
    )


def files_folder(ctx: AppContext, route: Route) -> ft.Control:
    """Once, at the start: the folder where the backup files go, so that they can be found again and imported."""
    suggestion = services.suggested_folder()
    error = W.error_text()

    def chosen(path: str) -> None:
        try:
            services.set_backup_folder(ctx.folder, path)
        except OSError as problem:
            error.value = f"Non riesco a usare questa cartella: {problem}"
            ctx.update(error)
            return
        ctx.advance()

    def create(_: Any) -> None:
        def answered(granted: bool) -> None:
            if not granted:
                error.value = "Senza il permesso non posso creare la cartella. Puoi darlo dalle impostazioni del telefono, oppure scegliere tu una cartella con il pulsante «Scelgo io la cartella»."
                ctx.update(error)
                return
            try:
                services.create_suggested_folder(ctx.folder)
            except OSError as problem:
                error.value = f"Non sono riuscito a creare la cartella: {problem}. Scegline una tu."
                ctx.update(error)
                return
            ctx.toast(f"Cartella creata: {suggestion}")
            ctx.advance()

        ctx.ask_files_permission(answered)

    def without(_: Any) -> None:
        def confirmed() -> None:
            services.save_ui_settings(ctx.folder, backup_files_folder="")
            ctx.advance()

        ctx.confirm(
            "Continuare senza backup?",
            "Senza una cartella non faccio nessun backup. Se perdi il telefono, lo rompi o disinstalli l'app, i tuoi dati si perdono per sempre. Potrai scegliere la cartella quando vuoi da Impostazioni · Mnemosyne, e finché non lo fai ti ricordo che sei senza backup.",
            "Continuo senza backup",
            confirmed,
            cancel_label="Torno indietro",
        )

    return W.screen(
        [
            _brand(),
            W.title_with_nickname("Dove salvo i tuoi backup?", "Mnemosyne", size=22),
            W.panel(
                ft.Column(
                    [
                        W.body("I backup li metto in una cartella che vedi e controlli tu, così se cambi telefono o disinstalli l'app non perdi niente. Senza questa cartella i backup automatici non possono partire."),
                        W.body(f"Ti consiglio {bf.SUGGESTED} nella memoria principale del telefono, perché è facile da ritrovare con il gestore di file: {suggestion}", dim=True, selectable=True),
                        W.caption("Per crearla ti chiederò il permesso di accedere ai file. Se non lo dai, puoi scegliere tu una cartella."),
                    ],
                    spacing=8,
                )
            ),
            error,
            ft.Row(
                [W.primary_button("Crea la cartella per me", create, icon="CREATE_NEW_FOLDER"), W.secondary_button("Scelgo io la cartella", lambda _: ctx.pick_folder(chosen), icon="FOLDER_OPEN")],
                alignment=ft.MainAxisAlignment.END,
                wrap=True,
                spacing=8,
            ),
            ft.Row([W.danger_button("Continua senza backup", without)], alignment=ft.MainAxisAlignment.END),
        ],
        ctx.wide,
    )


def diario(ctx: AppContext, route: Route) -> ft.Control:
    """The first start: every pack there is, with a box each; the base ones come ticked."""
    boxes: Dict[str, ft.Checkbox] = {}
    for pack in builtin_packs():
        box = ft.Checkbox(label=f"{pack.name}", value=pack.short_name in BASE_PACKS, active_color=T.ACCENT)
        boxes[pack.short_name] = box

    def later(_: Any) -> None:
        services.save_ui_settings(ctx.folder, diario_suggested=True)
        ctx.advance()

    def install(_: Any) -> None:
        chosen = [name for name, box in boxes.items() if box.value]
        try:
            with ctx.store() as store:
                added = install_base_packs(store, chosen)
        except (StoreError, ValueError) as problem:
            ctx.toast(str(problem), error=True)
            return
        services.save_ui_settings(ctx.folder, diario_suggested=True)
        ctx.data_changed()
        ctx.toast(f"Pacchetti installati: {len(added)}." if added else "I pacchetti scelti c'erano già.")
        ctx.advance()

    return W.screen(
        [
            _brand(),
            *_found_backup(ctx),
            W.title_with_nickname("Da dove partiamo?", "Stoa", size=22),
            W.panel(
                ft.Column(
                    [
                        W.body("Scegli i pacchetti di modelli da installare: quelli di base sono già spuntati."),
                        ft.Column(list(boxes.values()), spacing=0),
                        W.body("Puoi installarne altri o toglierli quando vuoi, da Modelli · Pacchetti.", dim=True),
                    ],
                    spacing=12,
                )
            ),
            ft.Row([W.secondary_button("Più tardi", later), W.primary_button("Installa i pacchetti scelti", install, icon="DOWNLOAD")], alignment=ft.MainAxisAlignment.END, wrap=True, spacing=8),
            W.body(APP_MOTTO, dim=True, italic=True, text_align=ft.TextAlign.CENTER),
        ],
        ctx.wide,
    )
