"""Theoria · Viste (0.2.8): saved filters over the entries, run on demand and shown as tiles in Oggi."""

from typing import Any, Callable, List

import flet as ft

from zibaldone.core import views as V
from zibaldone.core.areas import area_label
from zibaldone.core.brand import AREAS
from zibaldone.storage.database import StoreError
from zibaldone.ui import theme as T
from zibaldone.ui import viewmodels as vm
from zibaldone.ui import widgets as W
from zibaldone.ui.context import AppContext
from zibaldone.ui.navigation import Route
from zibaldone.ui.views.common import not_found

ANY = "*"  # a dropdown key for «tutti»: an empty key does not round-trip
ORDERS = ("Più recenti", "Titolo")


def installed(store: Any) -> bool:
    return store.find_template(V.TEMPLATE) is not None


def summary(view: V.View) -> str:
    """The filters of a view in one line, e.g. «libro · salute · «dune» · stato = In corso»."""
    parts = [view.template, area_label(view.area) if view.area else "", f"«{view.text}»" if view.text else "", f"{view.field} = {view.value}" if view.field else ""]
    return " · ".join(part for part in parts if part) or "tutte le voci"


def _install(ctx: AppContext) -> Callable[[Any], None]:
    def install(_: Any) -> None:
        from zibaldone.core.packs import apply_install, find_builtin_pack, plan_install

        try:
            with ctx.store() as store:
                pack = find_builtin_pack(V.PACK_NAME)
                if pack is None:
                    raise ValueError("il pacchetto «Theoria · Viste» non è ancora in questa versione")
                apply_install(plan_install(pack, store), store)
        except (StoreError, ValueError) as problem:
            ctx.toast(str(problem), error=True)
            return
        ctx.data_changed()
        ctx.toast("Theoria · Viste installato.")
        ctx.refresh()

    return install


def _new_dialog(ctx: AppContext, templates: List[Any]) -> None:
    name = W.text_input("", label="Nome della vista")
    template = W.dropdown([(ANY, "Tutti i modelli")] + [(item.slug, item.name) for item in templates], ANY, label="Modello")
    area = W.dropdown([(ANY, "Tutte le aree")] + [(key, area_label(key)) for key in AREAS], ANY, label="Area")
    text = W.text_input("", label="Testo da cercare")
    field = W.text_input("", label="Blocco (facoltativo)", hint_text="stato")
    value = W.text_input("", label="Valore del blocco", hint_text="In corso")
    order = W.dropdown([(item, item) for item in ORDERS], ORDERS[0], label="Ordine")
    error = W.error_text()

    def save(_: Any = None) -> None:
        def pick(control: ft.Dropdown) -> str:
            return "" if control.value in (None, ANY) else control.value

        try:
            with ctx.store() as store:
                V.save_view(store, name.value or "", template=pick(template), area=pick(area), text=text.value or "", field=field.value or "", value=value.value or "", order=order.value or ORDERS[0])
        except (V.ViewError, ValueError, StoreError) as problem:
            error.value, error.visible = str(problem), True
            ctx.update(error)
            return
        ctx.close_dialog()
        ctx.data_changed()
        ctx.toast("Vista salvata.")
        ctx.refresh()

    name.on_submit = save
    ctx.show_dialog(
        ft.AlertDialog(
            modal=True,
            title="Nuova vista",
            content=ft.Container(ft.Column([W.wide(name), template, area, W.wide(text), W.wide(field), W.wide(value), order, error], spacing=12, tight=True, scroll=ft.ScrollMode.AUTO), width=380),
            actions=[W.text_button("Annulla", ctx.close_dialog, color=T.TEXT), W.primary_button("Salva", save, icon="CHECK")],
        )
    )


def _delete(ctx: AppContext, view: V.View) -> Callable[[Any], None]:
    def remove() -> None:
        try:
            with ctx.store() as store:
                V.delete_view(store, view.id)
        except (V.ViewError, StoreError) as problem:
            ctx.toast(str(problem), error=True)
            return
        ctx.data_changed()
        ctx.toast("Vista tolta.")
        ctx.refresh()

    return lambda _: ctx.confirm("Togliere la vista?", f"«{view.name}» sparisce dall'elenco e da Oggi; le voci restano dove sono.", "Togli", remove)


def build_list(ctx: AppContext, route: Route) -> ft.Control:
    with ctx.store() as store:
        ready = installed(store)
        views = V.load_views(store) if ready else []
        templates = store.list_templates() if ready else []
    header = W.screen_header("Viste", "Theoria", "filtri salvati sulle tue voci, da aprire o da tenere in Oggi", on_back=ctx.back)
    if not ready:
        return W.screen(
            [
                header,
                W.panel(
                    ft.Column(
                        [
                            W.body("Salva un filtro (modello, area, testo, un blocco) e riaprilo quando vuoi, o mettilo in Oggi. Arriva con la Scuola «Theoria · Viste»."),
                            ft.Row([W.primary_button("Installa «Theoria · Viste»", _install(ctx), icon="DOWNLOAD")], alignment=ft.MainAxisAlignment.END),
                        ],
                        spacing=10,
                    ),
                    border_color=W.fade(T.ACCENT, 0.45),
                )
            ],
            ctx.wide,
        )
    controls: List[ft.Control] = [header, ft.Row([W.primary_button("Nuova vista", lambda _: _new_dialog(ctx, templates), icon="ADD")], alignment=ft.MainAxisAlignment.END)]
    if not views:
        controls.append(W.empty_state("Nessuna vista, per ora. Una buona prima: «i libri in corso».", "FILTER_ALT_OUTLINED"))
    for view in views:
        controls.append(
            W.panel(
                ft.Row(
                    [
                        ft.Column([W.body(view.name, size=15, weight=ft.FontWeight.W_600), W.caption(summary(view))], spacing=3, expand=True),
                        W.secondary_button("Apri", lambda _, view_id=view.id: ctx.go(f"/viste/{view_id}"), icon="OPEN_IN_NEW"),
                        W.icon_button("DELETE_OUTLINE", _delete(ctx, view), tooltip="Togli la vista"),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )
        )
    return W.screen(controls, ctx.wide)


def build_results(ctx: AppContext, route: Route) -> ft.Control:
    with ctx.store() as store:
        view = next((item for item in V.load_views(store) if item.id == route.arg), None) if installed(store) else None
        if view is None:
            return not_found(ctx, "Questa vista non esiste più.")
        templates = {template.slug: template for template in store.list_templates()}
        today = ctx.now().date()
        try:
            found = V.run_view(store, view)
            problem = ""
        except V.ViewError as error:
            found, problem = [], str(error)
    controls: List[ft.Control] = [W.screen_header(view.name, "Theoria", summary(view), on_back=ctx.back)]
    if problem:
        controls.append(W.caption(problem))
    rows = [vm.entry_row(entry, templates[entry.template], today) for entry in found if entry.template in templates]
    for row in rows:
        controls.append(W.entry_tile(row.title, row.template_name, row.summary, row.icon, row.color, lambda _, entry_id=row.id: ctx.go(f"/voci/{entry_id}")))
    if not rows and not problem:
        controls.append(W.empty_state("Nessuna voce corrisponde, per ora.", "FILTER_ALT_OFF"))
    return W.screen(controls, ctx.wide)
