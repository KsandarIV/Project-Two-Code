"""First run: privacy consent (Parresia), Google sign-in when required, the diary suggestion."""

from typing import Any, List

import flet as ft

from zibaldone.core.brand import APP_MOTTO, APP_NAME, APP_TAGLINE, NOMENCLATURE, mascot_for
from zibaldone.core.packs import BASE_PACKS, find_builtin_pack, install_base_packs
from zibaldone.core.privacy import NOTICE_VERSION, notice_text
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


def diario(ctx: AppContext, route: Route) -> ft.Control:
    names: List[ft.Control] = [W.pill(pack.name, T.ACCENT if index else T.ACCENT_2) for index, pack in enumerate(filter(None, (find_builtin_pack(name) for name in BASE_PACKS)))]

    def later(_: Any) -> None:
        services.save_ui_settings(ctx.folder, diario_suggested=True)
        ctx.advance()

    def install(_: Any) -> None:
        try:
            with ctx.store() as store:
                added = install_base_packs(store)
        except (StoreError, ValueError) as problem:
            ctx.toast(str(problem), error=True)
            return
        services.save_ui_settings(ctx.folder, diario_suggested=True)
        ctx.data_changed()
        ctx.toast(f"Pacchetti di base installati: {len(added)}." if added else "I pacchetti di base c'erano già.")
        ctx.advance()

    return W.screen(
        [
            _brand(),
            *_found_backup(ctx),
            W.title_with_nickname("Da dove partiamo?", "Stoa", size=22),
            W.panel(
                ft.Column(
                    [
                        W.body("Con un solo tocco arrivano il diario, le otto aree, le persone, le collezioni, le abitudini e le viste salvate."),
                        ft.Row(names, wrap=True, spacing=6, run_spacing=6),
                        W.body("Puoi cambiare tutto, togliere o aggiungere altre Scuole quando vuoi, da Modelli. Segreti e Finanze restano su richiesta.", dim=True),
                    ],
                    spacing=12,
                )
            ),
            ft.Row([W.secondary_button("Più tardi", later), W.primary_button("Inizia con i pacchetti di base", install, icon="DOWNLOAD")], alignment=ft.MainAxisAlignment.END, wrap=True, spacing=8),
            W.body(APP_MOTTO, dim=True, italic=True, text_align=ft.TextAlign.CENTER),
        ],
        ctx.wide,
    )
