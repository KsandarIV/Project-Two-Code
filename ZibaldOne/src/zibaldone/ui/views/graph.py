"""Rizoma (0.1.3): the graph of the links between entries, on a canvas you can tap."""

from typing import Any, List, Optional

import flet as ft
import flet.canvas as cv

from zibaldone.core.brand import NOMENCLATURE
from zibaldone.storage.database import StoreError
from zibaldone.ui import theme as T
from zibaldone.ui import viewmodels as vm
from zibaldone.ui import widgets as W
from zibaldone.ui.context import AppContext
from zibaldone.ui.navigation import Route
from zibaldone.ui.views.common import not_found

ALL = "*"
HEIGHT_WIDE, HEIGHT_NARROW = 560, 420
# Until the canvas reports its size: a good guess for each layout.
GUESS_WIDE, GUESS_NARROW = 820, 340


class GraphScreen:
    def __init__(self, ctx: AppContext, route: Route) -> None:
        self.ctx = ctx
        self.around = route.arg
        self.query: vm.GraphQuery = ctx.memory.setdefault("graph_query", vm.GraphQuery())
        self.height = HEIGHT_WIDE if ctx.wide else HEIGHT_NARROW
        self.size = (GUESS_WIDE if ctx.wide else GUESS_NARROW, self.height)
        self.graph: Any = None
        self.drawing: Optional[vm.GraphDrawing] = None
        self.canvas = cv.Canvas([], height=self.height, on_resize=self.resized)
        self.summary = W.caption("")
        self.legend = ft.Row([], wrap=True, spacing=6, run_spacing=6)
        self.hubs = ft.Column([], spacing=10, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        self.picture = ft.Container()

    def build(self) -> ft.Control:
        center_title = ""
        try:
            with self.ctx.store() as store:
                templates = store.list_templates()
                if self.around:
                    center_title = vm.entry_detail(store, self.around, self.ctx.now().date(), mentions=0).title
                    self.around = store.get_entry(self.around).id
        except StoreError:
            return not_found(self.ctx, "Questa voce non esiste più, quindi non c'è un grafo intorno a lei.")
        name = NOMENCLATURE["graph"]
        subtitle = f"intorno a «{center_title}»" if center_title else name.meaning
        options = [(ALL, "Tutti i modelli")] + [(template.slug, template.name) for template in templates]
        filters: List[ft.Control] = [
            ft.ResponsiveRow(
                [
                    ft.Container(ft.Row([W.dropdown(options, self.query.template or ALL, label="Modello", on_select=self.template_changed, expand=True)]), col={"xs": 12, "md": 6}),
                    ft.Container(
                        ft.Row([W.dropdown([("1", "1 passo"), ("2", "2 passi"), ("3", "3 passi")], str(self.query.depth), label="Distanza", on_select=self.depth_changed, expand=True)]),
                        col={"xs": 12, "md": 6},
                        visible=bool(self.around),
                    ),
                ],
                spacing=12,
                run_spacing=12,
            ),
            ft.Row(
                [
                    self._switch("Voci senza collegamenti", self.query.isolated, "isolated"),
                    self._switch("[[Titoli]] senza voce", self.query.unresolved, "unresolved"),
                ],
                wrap=True,
                spacing=16,
                run_spacing=8,
            ),
        ]
        actions = [W.secondary_button("Tutto il grafo", lambda _: self.ctx.go("/grafo"), icon="HUB")] if self.around else []
        self.picture = ft.Container(
            ft.GestureDetector(content=self.canvas, on_tap_down=self.tapped, mouse_cursor=ft.MouseCursor.CLICK),
            bgcolor=T.BG,
            border=ft.Border.all(1, T.BORDER),
            border_radius=T.RADIUS,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
        )
        self.reload(update=False)
        return W.screen(
            [
                W.screen_header(name.name, "", subtitle, on_back=self.ctx.back if self.around else None, actions=actions),
                W.panel(ft.Column(filters, spacing=12), padding=14),
                self.summary,
                self.picture,
                self.legend,
                W.caption("Tocca un punto per aprire la voce. Le linee sono i collegamenti: i blocchi «collegamento» e i [[Titoli]] scritti nei testi."),
                self.hubs,
            ],
            self.ctx.wide,
        )

    def _switch(self, label: str, value: bool, which: str) -> ft.Switch:
        def changed(event: Any) -> None:
            setattr(self.query, which, bool(event.control.value))
            self.reload()

        return ft.Switch(label=label, value=value, active_color=T.ACCENT, label_text_style=ft.TextStyle(color=T.TEXT, size=15), on_change=changed)

    # — filters —

    def template_changed(self, event: Any) -> None:
        value = event.control.value
        self.query.template = "" if value in (None, ALL) else value
        self.reload()

    def depth_changed(self, event: Any) -> None:
        try:
            self.query.depth = int(event.control.value or 1)
        except ValueError:
            self.query.depth = 1
        self.reload()

    # — drawing —

    def reload(self, update: bool = True) -> None:
        with self.ctx.store() as store:
            self.graph = vm.load_graph(store, self.query, self.around)
        self.summary.value = vm.graph_summary(self.graph)
        self.legend.controls = [W.pill(name, color) for _, name, color in self.graph.legend]
        self.picture.visible = bool(self.graph.nodes)
        self._hub_list()
        self.redraw(update=False)
        if update:
            self.ctx.update()

    def _hub_list(self) -> None:
        facts = self.graph.facts
        controls: List[ft.Control] = []
        if not facts.entries:
            hint = "Nessuna voce con questi filtri." if (self.query.template or self.around) else "Ancora niente da collegare: scrivi qualche voce."
            controls.append(W.empty_state(hint, "HUB"))
        elif not facts.edges:
            controls.append(W.empty_state("Nessun collegamento ancora. Scrivi [[Titolo]] in un testo, o usa un blocco «collegamento» (per esempio «Con chi» nell'incontro).", "HUB"))
        hubs = [(node_id, label, degree) for node_id, label, degree in facts.hubs if degree > 0][:5]
        if hubs:
            controls.append(W.body("Le più collegate", size=16, weight=ft.FontWeight.W_600))
            for node_id, label, degree in hubs:
                node = self.graph.node(node_id)
                color = node.color if node and node.color else T.ACCENT
                meta = "1 collegamento" if degree == 1 else f"{degree} collegamenti"
                controls.append(W.entry_tile(label, meta, "", "HUB", color, lambda _, target=node_id: self.open_node(target)))
        self.hubs.controls = controls

    def resized(self, event: Any) -> None:
        width, height = float(getattr(event, "width", 0) or 0), float(getattr(event, "height", 0) or 0)
        if width <= 0 or height <= 0 or (abs(width - self.size[0]) < 1 and abs(height - self.size[1]) < 1):
            return
        self.size = (width, height)
        self.redraw()

    def redraw(self, update: bool = True) -> None:
        self.drawing = vm.draw_graph(self.graph, self.size[0], self.size[1], self.around)
        shapes: List[cv.Shape] = []
        for edge in self.drawing.edges:
            shapes.append(cv.Line(edge.x1, edge.y1, edge.x2, edge.y2, paint=ft.Paint(color=edge.color, stroke_width=edge.width, style=ft.PaintingStyle.STROKE)))
        for node in self.drawing.nodes:
            if node.center:
                shapes.append(cv.Circle(node.x, node.y, node.radius + 5, paint=ft.Paint(color=W.fade(T.ACCENT, 0.35), style=ft.PaintingStyle.FILL)))
            if node.kind == "missing":
                shapes.append(cv.Circle(node.x, node.y, node.radius, paint=ft.Paint(color=node.color, stroke_width=1.5, style=ft.PaintingStyle.STROKE)))
            else:
                shapes.append(cv.Circle(node.x, node.y, node.radius, paint=ft.Paint(color=node.color, style=ft.PaintingStyle.FILL)))
        for node in self.drawing.nodes:
            if node.label:
                shapes.append(
                    cv.Text(
                        node.x,
                        node.y + node.radius + 3,
                        node.label,
                        style=ft.TextStyle(size=11, color=T.TEXT if node.kind == "entry" else T.TEXT_DIM),
                        alignment=ft.Alignment.TOP_CENTER,
                    )
                )
        self.canvas.shapes = shapes
        if update:
            self.ctx.update(self.canvas)

    # — taps —

    def tapped(self, event: Any) -> None:
        position = getattr(event, "local_position", None)
        if position is None or self.drawing is None:
            return
        node = vm.nearest_node(self.drawing, position.x, position.y)
        if node is not None:
            self.open_node(node.id)

    def open_node(self, node_id: str) -> None:
        node = self.graph.node(node_id) if self.graph else None
        if node is None:
            return
        if node.kind == "entry":
            self.ctx.go(f"/voci/{node.id}")
        elif node.kind == "missing":
            self.ctx.toast(f"«{node.label}» non ha ancora una voce: quando la scrivi, si collega da sola.")


def build(ctx: AppContext, route: Route) -> ft.Control:
    return GraphScreen(ctx, route).build()
