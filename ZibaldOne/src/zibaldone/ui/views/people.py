"""Agorà: everything about one person, area by area (0.2.1); the family tree and the network of people (0.2.2)."""

from typing import Any, List, Optional, Tuple

import flet as ft
import flet.canvas as cv

from zibaldone.core.people import QUICK_KINDS, PeopleError
from zibaldone.storage.database import StoreError
from zibaldone.ui import theme as T
from zibaldone.ui import viewmodels as vm
from zibaldone.ui import widgets as W
from zibaldone.ui.context import AppContext
from zibaldone.ui.navigation import Route
from zibaldone.ui.views.common import not_found
from zibaldone.ui.views.graph import canvas_shapes

QUICK_ICONS = {"Chiamata": "CALL", "Messaggi": "CHAT", "Di persona": "PEOPLE"}


def build_person(ctx: AppContext, route: Route) -> ft.Control:
    with ctx.store() as store:
        view = vm.person_view(store, route.arg, ctx.now().date())
    if view is None:
        return not_found(ctx, "Questa persona non c'è più, o non è una persona.")
    actions = [W.secondary_button("Modifica", lambda _: ctx.go(f"/voci/{view.id}/modifica"), icon="EDIT")]
    subtitle = " · ".join(part for part in (view.roles, view.nicknames and f"detto {view.nicknames}") if part)
    controls: List[ft.Control] = [W.screen_header(view.name, "Agorà", subtitle, on_back=ctx.back, actions=actions)]
    if view.areas:
        controls.append(
            ft.Row([ft.Container(W.pill(label, color), on_click=lambda _, key=key: ctx.go(f"/aree/{key}")) for key, label, color in view.areas], wrap=True, spacing=6)
        )
    if view.details:
        rows = []
        for label, value, url in view.details:
            text: ft.Control = W.text_button(value, lambda _, url=url: ctx.open_url(url)) if url else W.body(value)
            rows.append(ft.Row([ft.Container(W.caption(label), width=96), text], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER))
        controls.append(W.panel(ft.Column(rows, spacing=4)))
    controls.append(_contacts(ctx, view))
    controls.append(_ties(ctx, view))
    for group in view.groups:
        tiles: List[ft.Control] = [W.body(f"{group.label} ({len(group.rows)})", size=16, weight=ft.FontWeight.W_600)]
        tiles += [_tile(ctx, row) for row in group.rows]
        controls.append(W.panel(ft.Column(tiles, spacing=10), border_color=W.fade(group.color, 0.45)))
    if view.mentions:
        tiles = [W.body("La nominano senza collegamento", size=16, weight=ft.FontWeight.W_600)]
        tiles += [_tile(ctx, row) for row in view.mentions]
        controls.append(W.panel(ft.Column(tiles, spacing=10)))
    if not view.groups and not view.mentions:
        controls.append(W.caption(f"Ancora nessuna voce collega {view.name}. Scrivi [[{view.name}]] in un testo, o segna un incontro."))
    return W.screen(controls, ctx.wide)


def _tile(ctx: AppContext, row: vm.EntryRow) -> ft.Control:
    return W.entry_tile(row.title, f"{row.template_name} · {row.day_label}", row.summary, row.icon, row.color, lambda _, entry_id=row.id: ctx.go(f"/voci/{entry_id}"))


def _contacts(ctx: AppContext, view: vm.PersonView) -> ft.Control:
    head: List[ft.Control] = [W.body("Contatti", size=16, weight=ft.FontWeight.W_600), ft.Container(expand=True)]
    if view.due:
        head.append(W.pill("da sentire", T.ACCENT_2, icon="WAVING_HAND"))
    rows: List[ft.Control] = [ft.Row(head, vertical_alignment=ft.CrossAxisAlignment.CENTER), W.caption(view.contact)]
    for line in (view.rhythm, view.strength):
        if line:
            rows.append(W.caption(line))
    if view.can_log:
        rows.append(
            ft.Row(
                [W.secondary_button(kind, lambda _, kind=kind: _log(ctx, view, kind), icon=QUICK_ICONS[kind]) for kind in QUICK_KINDS],
                wrap=True,
                spacing=8,
            )
        )
    for contact in view.contacts:
        rows.append(
            ft.Container(
                ft.Row(
                    [
                        ft.Icon(W.icon_of(contact.icon), size=18, color=T.ACCENT),
                        ft.Column([W.body(contact.title, size=14), W.caption(" · ".join(part for part in (contact.label, contact.day_label, contact.note) if part))], spacing=0, expand=True),
                    ],
                    spacing=10,
                ),
                on_click=lambda _, entry_id=contact.entry_id: ctx.go(f"/voci/{entry_id}"),
            )
        )
    return W.panel(ft.Column(rows, spacing=8))


def _ties(ctx: AppContext, view: vm.PersonView) -> ft.Control:
    buttons: List[ft.Control] = [ft.Container(expand=True)]
    if view.in_family:
        buttons.append(W.text_button("Albero", lambda _: ctx.go("/albero"), icon="ACCOUNT_TREE"))
    buttons.append(W.text_button("Rete", lambda _: ctx.go("/rete"), icon="HUB"))
    head = ft.Row([W.body(f"Legami ({len(view.ties)})", size=16, weight=ft.FontWeight.W_600), *buttons], vertical_alignment=ft.CrossAxisAlignment.CENTER)
    rows: List[ft.Control] = [head]
    for tie in view.ties:
        meta = " · ".join(part for part in (tie.how, tie.common) if part)
        rows.append(
            ft.Container(
                ft.Column([W.body(tie.name, size=15, weight=ft.FontWeight.W_600), W.caption(meta)], spacing=0),
                on_click=lambda _, person_id=tie.id: ctx.go(f"/persone/{person_id}"),
            )
        )
    if not view.ties:
        rows.append(W.caption(f"Genitori, fratelli, colleghi e chi conosce: si scrivono in Modifica. Chi incontri insieme a {view.name} si lega da solo."))
    return W.panel(ft.Column(rows, spacing=8))


def _log(ctx: AppContext, view: vm.PersonView, kind: str) -> None:
    try:
        with ctx.store() as store:
            entry = vm.log_person_contact(store, view.id, kind)
    except (PeopleError, StoreError, ValueError) as problem:
        ctx.toast(str(problem), error=True)
        return
    ctx.data_changed()
    ctx.toast(f"Segnato: {entry.values.get('titolo')}.", action="Racconta", on_action=lambda: ctx.go(f"/voci/{entry.id}/modifica"))
    ctx.refresh()


# * — the family tree (0.2.2) —


def build_tree(ctx: AppContext, route: Route) -> ft.Control:
    with ctx.store() as store:
        rows = vm.family_tree_rows(store)
    controls: List[ft.Control] = [W.screen_header("Albero di famiglia", "Agorà", "la famiglia generazione per generazione", on_back=ctx.back)]
    for row in rows:
        tiles: List[ft.Control] = [W.body(row.label, size=16, weight=ft.FontWeight.W_600)]
        for member in row.members:
            if member.id:
                tiles.append(W.entry_tile(member.name, member.caption or "in famiglia", "", "PERSON", member.color, lambda _, person_id=member.id: ctx.go(f"/persone/{person_id}")))
            else:
                tiles.append(W.panel(ft.Row([W.pill(member.name, member.color, icon="STAR"), W.caption(member.caption)], spacing=10, wrap=True)))
        controls.append(W.panel(ft.Column(tiles, spacing=8), border_color=W.fade(T.ACCENT, 0.3)))
    if not rows:
        controls.append(W.empty_state("Ancora nessun familiare. Dai a una persona un ruolo (madre, nonno …) o i suoi Genitori, e l'albero si disegna da solo.", "ACCOUNT_TREE"))
    else:
        controls.append(W.caption("La generazione viene dai ruoli (madre, nonno, figlia …) e dai Genitori e Fratelli scritti nelle persone. Chi non ha né l'uno né l'altro sta nella tua."))
    return W.screen(controls, ctx.wide)


# * — the network of people (0.2.2) —

HEIGHT_WIDE, HEIGHT_NARROW = 520, 380
GUESS_WIDE, GUESS_NARROW = 820, 340


class NetworkScreen:
    def __init__(self, ctx: AppContext, route: Route) -> None:
        self.ctx = ctx
        self.area = route.arg
        height = HEIGHT_WIDE if ctx.wide else HEIGHT_NARROW
        self.size: Tuple[float, float] = (GUESS_WIDE if ctx.wide else GUESS_NARROW, height)
        self.view: Optional[vm.NetworkView] = None
        self.drawing: Optional[vm.GraphDrawing] = None
        self.canvas = cv.Canvas([], height=height, on_resize=self.resized)

    def build(self) -> ft.Control:
        with self.ctx.store() as store:
            self.view = vm.network_view(store, self.area, self.ctx.now().date())
        view = self.view
        actions = [W.secondary_button("Tutte le persone", lambda _: self.ctx.go("/rete"), icon="HUB")] if self.area else []
        controls: List[ft.Control] = [W.screen_header(view.title, "Agorà", "chi conosce chi tra le tue persone", on_back=self.ctx.back, actions=actions), W.caption(view.summary)]
        if view.graph.nodes:
            self.redraw(update=False)
            controls.append(
                ft.Container(
                    ft.GestureDetector(content=self.canvas, on_tap_down=self.tapped, mouse_cursor=ft.MouseCursor.CLICK),
                    bgcolor=T.BG,
                    border=ft.Border.all(1, T.BORDER),
                    border_radius=T.RADIUS,
                    clip_behavior=ft.ClipBehavior.HARD_EDGE,
                )
            )
            controls.append(ft.Row([W.pill(name, color) for _, name, color in view.graph.legend], wrap=True, spacing=6, run_spacing=6))
            controls.append(W.caption("Tocca una persona per aprirla. Le linee sono i legami (famiglia, colleghi, chi si conosce) e gli incontri fatti insieme: più sono, più la linea è spessa."))
        else:
            controls.append(W.empty_state("Ancora nessuna persona qui. Aggiungine una con il modello L'Altro.", "HUB"))
        if view.strongest:
            tiles: List[ft.Control] = [W.body("Legami più forti", size=16, weight=ft.FontWeight.W_600)]
            for row in view.strongest:
                tiles.append(W.entry_tile(row.name, f"{row.score} · {row.meta}", "", "FAVORITE_OUTLINE", T.ACCENT, lambda _, person_id=row.id: self.ctx.go(f"/persone/{person_id}")))
            tiles.append(W.caption("La forza del legame (0–10) viene da quanto spesso e quanto di recente vi sentite, e dall'umore degli incontri quando c'è."))
            controls.append(ft.Column(tiles, spacing=10, horizontal_alignment=ft.CrossAxisAlignment.STRETCH))
        return W.screen(controls, self.ctx.wide)

    def resized(self, event: Any) -> None:
        width, height = float(getattr(event, "width", 0) or 0), float(getattr(event, "height", 0) or 0)
        if width <= 0 or height <= 0 or (abs(width - self.size[0]) < 1 and abs(height - self.size[1]) < 1):
            return
        self.size = (width, height)
        self.redraw()

    def redraw(self, update: bool = True) -> None:
        if self.view is None:
            return
        self.drawing = vm.draw_graph(self.view.graph, self.size[0], self.size[1])
        self.canvas.shapes = canvas_shapes(self.drawing)
        if update:
            self.ctx.update(self.canvas)

    def tapped(self, event: Any) -> None:
        position = getattr(event, "local_position", None)
        if position is None or self.drawing is None:
            return
        node = vm.nearest_node(self.drawing, position.x, position.y)
        if node is not None:
            self.ctx.go(f"/persone/{node.id}")


def build_network(ctx: AppContext, route: Route) -> ft.Control:
    return NetworkScreen(ctx, route).build()
