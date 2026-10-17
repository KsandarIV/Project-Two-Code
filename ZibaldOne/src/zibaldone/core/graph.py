"""Rizoma (il grafo, 0.1.3): entries as nodes, links (and optionally tags) as edges.

Plain data in, plain data out. The layout is a deterministic force-directed
one (Fruchterman–Reingold with a grid for repulsion, fixed seed, capped
iterations), each connected group laid out on its own and then packed;
positions are normalised to 0..1, so the HTML export here and the Flet
canvas of the UI draw exactly the same picture.
"""

import hashlib
import html
import json
import math
from collections import deque
from dataclasses import asdict, dataclass, field, replace
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from zibaldone.core.blocks import parse_day
from zibaldone.core.links import LinkRecord, name_key
from zibaldone.core.templates import Entry, Template

PALETTE = ("#B3F3F6", "#FF5500", "#FFFF00", "#FF0000", "#74EE15", "#FF007F", "#8A2BE2")
THEME = {
    "background": "#0D0E15",
    "panel": "#141521",
    "text": "#E6F7FF",
    "accent": "#00E5FF",
    "muted": "#8A93A6",
    "line": "#2A2D40",
}
TAG_COLOR = THEME["accent"]
TEMPLATE_COLOR = THEME["text"]
MISSING_COLOR = "#5A6275"
SEED = 7
MAX_ITERATIONS = 300
CLIQUE_LIMIT = 6  # shared tags: up to this many entries all linked together, beyond it a chain by date

NODE_ENTRY, NODE_TAG, NODE_TEMPLATE, NODE_MISSING = "entry", "tag", "template", "missing"
EDGE_BLOCK, EDGE_WIKI, EDGE_TAG, EDGE_TEMPLATE, EDGE_SHARED = "block", "wiki", "tag", "template", "shared_tag"
EDGE_PRIORITY = {EDGE_BLOCK: 0, EDGE_WIKI: 1, EDGE_SHARED: 2, EDGE_TAG: 3, EDGE_TEMPLATE: 4}


@dataclass
class GraphFilters:
    templates: Sequence[str] = ()
    since: Optional[str] = None
    until: Optional[str] = None
    tag: Optional[str] = None
    around: Optional[str] = None  # an entry id: only what is within `depth` links of it
    depth: int = 1
    tag_nodes: bool = False
    template_nodes: bool = False
    shared_tags: bool = False
    unresolved: bool = False
    isolated: bool = True


@dataclass
class GraphNode:
    id: str
    kind: str
    label: str
    color: str
    template: str = ""
    day: str = ""
    degree: int = 0
    component: int = 0
    x: float = 0.5
    y: float = 0.5


@dataclass
class GraphEdge:
    source: str
    target: str
    kind: str
    weight: int = 1
    label: str = ""


@dataclass
class GraphFacts:
    entries: int
    nodes: int
    edges: int
    components: int
    largest_component: int
    hubs: List[Tuple[str, str, int]]  # (id, label, degree), most connected first
    isolated: List[Tuple[str, str]]  # (id, label) of entries with no edge at all
    unresolved: int


@dataclass
class Graph:
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    facts: GraphFacts
    legend: List[Tuple[str, str, str]] = field(default_factory=list)  # (template slug, name, color)

    def node(self, node_id: str) -> Optional[GraphNode]:
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "format": 1,
            "nodes": [asdict(node) for node in self.nodes],
            "edges": [asdict(edge) for edge in self.edges],
            "facts": asdict(self.facts),
            "legend": [{"template": slug, "name": name, "color": color} for slug, name, color in self.legend],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=1)


# — building —


def _clean_tag(tag: str) -> str:
    return " ".join(tag.strip().lstrip("#").lower().split())


def _entry_filter(entries: Sequence[Entry], filters: GraphFilters, tags_by_entry: Dict[str, List[str]]) -> List[Entry]:
    since = parse_day(filters.since) if filters.since else None
    until = parse_day(filters.until) if filters.until else None
    wanted_tag = _clean_tag(filters.tag) if filters.tag else None
    chosen = []
    for entry in entries:
        if filters.templates and entry.template not in filters.templates:
            continue
        if (since and entry.day < since) or (until and entry.day > until):
            continue
        if wanted_tag and wanted_tag not in tags_by_entry.get(entry.id, []):
            continue
        chosen.append(entry)
    return chosen


def _shared_tag_pairs(entries: Sequence[Entry], tags_by_entry: Dict[str, List[str]]) -> List[Tuple[str, str, str]]:
    by_tag: Dict[str, List[Entry]] = {}
    for entry in entries:
        for tag in tags_by_entry.get(entry.id, []):
            by_tag.setdefault(tag, []).append(entry)
    pairs = []
    for tag in sorted(by_tag):
        group = sorted(by_tag[tag], key=lambda entry: (entry.day, entry.id))
        if len(group) <= CLIQUE_LIMIT:
            pairs += [(a.id, b.id, tag) for index, a in enumerate(group) for b in group[index + 1:]]
        else:
            pairs += [(a.id, b.id, tag) for a, b in zip(group, group[1:])]
    return pairs


def _neighbourhood(center: str, allowed: Set[str], pairs: Iterable[Tuple[str, str]], depth: int) -> Set[str]:
    adjacency: Dict[str, Set[str]] = {}
    for a, b in pairs:
        if a in allowed and b in allowed:
            adjacency.setdefault(a, set()).add(b)
            adjacency.setdefault(b, set()).add(a)
    seen = {center}
    queue = deque([(center, 0)])
    while queue:
        node, distance = queue.popleft()
        if distance >= depth:
            continue
        for other in sorted(adjacency.get(node, ())):
            if other not in seen:
                seen.add(other)
                queue.append((other, distance + 1))
    return seen


def template_colors(slugs: Iterable[str]) -> Dict[str, str]:
    """Palette colours by template, in alphabetical order of slug (stable between exports)."""
    return {slug: PALETTE[index % len(PALETTE)] for index, slug in enumerate(sorted(set(slugs)))}


def build_graph(
    entries: Sequence[Entry],
    templates: Dict[str, Template],
    links: Sequence[LinkRecord],
    tags_by_entry: Optional[Dict[str, List[str]]] = None,
    filters: Optional[GraphFilters] = None,
    seed: int = SEED,
    iterations: Optional[int] = None,
) -> Graph:
    filters = filters or GraphFilters()
    tags_by_entry = tags_by_entry or {}
    entries = [entry for entry in entries if entry.template in templates]
    by_id = {entry.id: entry for entry in entries}
    chosen = _entry_filter(entries, filters, tags_by_entry)
    if filters.around:
        if filters.around not in by_id:
            raise ValueError("la voce al centro del grafo non esiste")
        allowed = {entry.id for entry in chosen} | {filters.around}
        pairs = [(link.source, link.target) for link in links if link.target]
        if filters.shared_tags:
            pairs += [(a, b) for a, b, _ in _shared_tag_pairs([by_id[i] for i in allowed], tags_by_entry)]
        keep = _neighbourhood(filters.around, allowed, pairs, max(0, filters.depth))
        chosen = [by_id[entry_id] for entry_id in sorted(keep, key=lambda i: (by_id[i].day, i))]
    kept = {entry.id for entry in chosen}
    colors = template_colors(entry.template for entry in chosen)
    nodes: Dict[str, GraphNode] = {}
    for entry in sorted(chosen, key=lambda entry: (entry.day, entry.id)):
        template = templates[entry.template]
        nodes[entry.id] = GraphNode(entry.id, NODE_ENTRY, entry.title(template), colors[entry.template], entry.template, entry.day)

    merged: Dict[Tuple[str, str], GraphEdge] = {}

    def add_edge(source: str, target: str, kind: str, label: str = "") -> None:
        if source == target:
            return
        key = (source, target) if source < target else (target, source)
        edge = merged.get(key)
        if edge is None:
            merged[key] = GraphEdge(source, target, kind, 1, label)
        else:
            edge.weight += 1
            if EDGE_PRIORITY[kind] < EDGE_PRIORITY[edge.kind]:
                edge.kind, edge.label = kind, label

    unresolved = 0
    for link in links:
        if link.source not in kept:
            continue
        if link.target:
            if link.target in kept:
                add_edge(link.source, link.target, EDGE_BLOCK if link.kind == "block" else EDGE_WIKI)
        else:
            unresolved += 1
            if filters.unresolved and link.target_title:
                ghost = f"missing:{name_key(link.target_title)}"
                if ghost not in nodes:
                    nodes[ghost] = GraphNode(ghost, NODE_MISSING, link.target_title, MISSING_COLOR)
                add_edge(link.source, ghost, EDGE_WIKI if link.kind == "wiki" else EDGE_BLOCK)
    if filters.shared_tags:
        for a, b, tag in _shared_tag_pairs(chosen, tags_by_entry):
            add_edge(a, b, EDGE_SHARED, tag)
    if filters.tag_nodes:
        for entry in chosen:
            for tag in tags_by_entry.get(entry.id, []):
                tag_id = f"tag:{tag}"
                nodes.setdefault(tag_id, GraphNode(tag_id, NODE_TAG, f"#{tag}", TAG_COLOR))
                add_edge(entry.id, tag_id, EDGE_TAG, tag)
    if filters.template_nodes:
        for entry in chosen:
            template_id = f"template:{entry.template}"
            nodes.setdefault(template_id, GraphNode(template_id, NODE_TEMPLATE, templates[entry.template].name, TEMPLATE_COLOR, entry.template))
            add_edge(entry.id, template_id, EDGE_TEMPLATE)

    edges = sorted(merged.values(), key=lambda edge: (edge.source, edge.target))
    neighbours: Dict[str, Set[str]] = {node_id: set() for node_id in nodes}
    for edge in edges:
        neighbours[edge.source].add(edge.target)
        neighbours[edge.target].add(edge.source)
    for node_id, node in nodes.items():
        node.degree = len(neighbours[node_id])
    isolated = [(node.id, node.label) for node in nodes.values() if node.kind == NODE_ENTRY and node.degree == 0]
    if not filters.isolated:
        nodes = {node_id: node for node_id, node in nodes.items() if node.degree > 0}
    ordered = list(nodes.values())
    _place(ordered, edges, seed, iterations)
    groups = _components([node.id for node in ordered], [(edge.source, edge.target) for edge in edges])
    hubs = sorted((node for node in ordered if node.kind == NODE_ENTRY and node.degree > 0), key=lambda node: (-node.degree, node.label, node.id))
    facts = GraphFacts(
        entries=sum(1 for node in ordered if node.kind == NODE_ENTRY),
        nodes=len(ordered),
        edges=len(edges),
        components=len(groups),
        largest_component=len(groups[0]) if groups else 0,
        hubs=[(node.id, node.label, node.degree) for node in hubs[:10]],
        isolated=isolated,
        unresolved=unresolved,
    )
    legend = [(slug, templates[slug].name, color) for slug, color in colors.items()]
    return Graph(nodes=ordered, edges=edges, facts=facts, legend=legend)


def graph_from_store(store: Any, filters: Optional[GraphFilters] = None, seed: int = SEED, iterations: Optional[int] = None) -> Graph:
    """Build the graph from a `Store` (entries, templates, links and tags)."""
    filters = replace(filters) if filters else GraphFilters()
    if filters.around:
        filters.around = store.get_entry(filters.around).id
    templates = {template.slug: template for template in store.list_templates()}
    return build_graph(store.list_entries(newest_first=False), templates, store.all_links(), store.tags_by_entry(), filters, seed, iterations)


# — graph facts —


def _components(node_ids: Sequence[str], pairs: Iterable[Tuple[str, str]]) -> List[List[str]]:
    """Connected groups, biggest first (ties: by first id)."""
    parent = {node_id: node_id for node_id in node_ids}

    def find(node: str) -> str:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    for a, b in pairs:
        if a in parent and b in parent:
            root_a, root_b = find(a), find(b)
            if root_a != root_b:
                parent[max(root_a, root_b)] = min(root_a, root_b)
    groups: Dict[str, List[str]] = {}
    for node_id in node_ids:
        groups.setdefault(find(node_id), []).append(node_id)
    return sorted((sorted(group) for group in groups.values()), key=lambda group: (-len(group), group[0]))


# — layout —


def _start(node_id: str, seed: int) -> Tuple[float, float]:
    digest = hashlib.blake2b(f"{seed}:{node_id}".encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest[:4], "big") / 2**32, int.from_bytes(digest[4:], "big") / 2**32


def default_iterations(size: int) -> int:
    return max(30, min(MAX_ITERATIONS, int(4000 / math.sqrt(max(size, 1)))))


def force_layout(
    node_ids: Sequence[str], pairs: Sequence[Tuple[int, int, int]], seed: int = SEED, iterations: Optional[int] = None
) -> List[Tuple[float, float]]:
    """Fruchterman–Reingold around the unit square; `pairs` are (index, index, weight).

    Repulsion only between nodes closer than 2k (grid of cells), so a step is
    about linear in the number of nodes. Same input, same output.
    """
    count = len(node_ids)
    if count == 0:
        return []
    if count == 1:
        return [(0.5, 0.5)]
    steps = iterations if iterations is not None else default_iterations(count)
    k = math.sqrt(1.0 / count)
    k2, cell = k * k, 2.0 * k
    reach = cell * cell
    xs, ys = [], []
    for node_id in node_ids:
        x, y = _start(node_id, seed)
        xs.append(x)
        ys.append(y)
    temperature = 0.1
    cooling = temperature / (steps + 1)
    gravity = k
    neighbours = ((0, 0), (1, 0), (-1, 1), (0, 1), (1, 1))
    for _ in range(steps):
        dx, dy = [0.0] * count, [0.0] * count
        grid: Dict[Tuple[int, int], List[int]] = {}
        for index in range(count):
            grid.setdefault((math.floor(xs[index] / cell), math.floor(ys[index] / cell)), []).append(index)
        for (cx, cy), members in grid.items():
            for ox, oy in neighbours:
                others = members if (ox, oy) == (0, 0) else grid.get((cx + ox, cy + oy))
                if not others:
                    continue
                same = others is members
                for position, i in enumerate(members):
                    xi, yi = xs[i], ys[i]
                    for j in (members[position + 1:] if same else others):
                        ddx, ddy = xi - xs[j], yi - ys[j]
                        distance2 = ddx * ddx + ddy * ddy
                        if distance2 >= reach:
                            continue
                        if distance2 < 1e-12:
                            ddx, ddy, distance2 = 1e-6 * (1 + (i % 7)), 1e-6 * (1 + (j % 5)), 1e-12
                        force = k2 / distance2
                        dx[i] += ddx * force
                        dy[i] += ddy * force
                        dx[j] -= ddx * force
                        dy[j] -= ddy * force
        for i, j, weight in pairs:
            ddx, ddy = xs[i] - xs[j], ys[i] - ys[j]
            distance = math.sqrt(ddx * ddx + ddy * ddy) or 1e-9
            force = distance / k * min(weight, 3)
            dx[i] -= ddx * force
            dy[i] -= ddy * force
            dx[j] += ddx * force
            dy[j] += ddy * force
        for index in range(count):
            # A weak pull to the centre instead of walls: no pile-ups on the borders.
            ddx = dx[index] - (xs[index] - 0.5) * gravity
            ddy = dy[index] - (ys[index] - 0.5) * gravity
            moved = math.sqrt(ddx * ddx + ddy * ddy)
            if moved > 0:
                step = min(moved, temperature) / moved
                xs[index] += ddx * step
                ys[index] += ddy * step
        temperature -= cooling
    return list(zip(xs, ys))


def _normalise(points: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """Fit into 0..1 keeping the proportions; the shorter side is centred."""
    if not points:
        return []
    low_x, high_x = min(x for x, _ in points), max(x for x, _ in points)
    low_y, high_y = min(y for _, y in points), max(y for _, y in points)
    span = max(high_x - low_x, high_y - low_y)
    if span <= 0:
        return [(0.5, 0.5) for _ in points]
    off_x = (1 - (high_x - low_x) / span) / 2
    off_y = (1 - (high_y - low_y) / span) / 2
    return [(round(off_x + (x - low_x) / span, 6), round(off_y + (y - low_y) / span, 6)) for x, y in points]


def _place(nodes: List[GraphNode], edges: Sequence[GraphEdge], seed: int, iterations: Optional[int]) -> None:
    """Lay out each connected group, then pack the groups in rows, biggest first."""
    index = {node.id: position for position, node in enumerate(nodes)}
    groups = _components([node.id for node in nodes], [(edge.source, edge.target) for edge in edges])
    group_of = {node_id: number for number, group in enumerate(groups) for node_id in group}
    edges_of: Dict[int, List[GraphEdge]] = {}
    for edge in edges:
        if edge.source in group_of and edge.target in group_of:
            edges_of.setdefault(group_of[edge.source], []).append(edge)
    boxes = []
    for number, group in enumerate(groups):
        local = {node_id: position for position, node_id in enumerate(group)}
        pairs = [(local[edge.source], local[edge.target], edge.weight) for edge in edges_of.get(number, [])]
        points = _normalise(force_layout(group, pairs, seed, iterations)) if len(group) > 1 else [(0.5, 0.5)]
        side = math.sqrt(len(group))
        boxes.append((group, points, side))
        for node_id in group:
            nodes[index[node_id]].component = number
    total = sum(side * side for _, _, side in boxes)
    row_width = max(math.sqrt(total) * 1.3, max((side for _, _, side in boxes), default=1.0))
    gap = 0.6
    cursor_x = cursor_y = row_height = 0.0
    placed: List[Tuple[str, float, float]] = []
    for group, points, side in boxes:
        if cursor_x > 0 and cursor_x + side > row_width:
            cursor_x, cursor_y, row_height = 0.0, cursor_y + row_height + gap, 0.0
        for node_id, (x, y) in zip(group, points):
            placed.append((node_id, cursor_x + x * side, cursor_y + y * side))
        cursor_x += side + gap
        row_height = max(row_height, side)
    final = _normalise([(x, y) for _, x, y in placed])
    for (node_id, _, _), (x, y) in zip(placed, final):
        nodes[index[node_id]].x, nodes[index[node_id]].y = x, y


# — HTML export —

PAGE_CSS = """
:root{color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:%(background)s;color:%(text)s;font:14px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
header,main{max-width:1200px;margin:0 auto;padding:16px}
h1{margin:0;font-size:22px;color:%(accent)s;letter-spacing:.02em}
h1 small{color:%(muted)s;font-weight:400;font-size:14px;margin-left:8px}
h2{font-size:15px;color:%(accent)s;margin:0 0 8px}
.panel{background:%(panel)s;border:1px solid %(line)s;border-radius:10px;padding:12px 14px}
.muted{color:%(muted)s}
.grid{display:grid;grid-template-columns:minmax(0,1fr) 280px;gap:16px}
@media (max-width:800px){.grid{grid-template-columns:minmax(0,1fr)}}
ul{margin:0;padding-left:18px}
li{margin:2px 0}
.swatch{display:inline-block;width:10px;height:10px;border-radius:50%%;margin-right:6px;vertical-align:baseline}
button{background:%(panel)s;color:%(text)s;border:1px solid %(line)s;border-radius:6px;padding:4px 10px;font:inherit;cursor:pointer}
button:hover,button:focus-visible{border-color:%(accent)s;outline:none}
"""


def esc(value: Any) -> str:
    """Every user string goes through here before reaching the HTML."""
    return html.escape(str(value), quote=True)


def html_page(title: str, subtitle: str, body: str, script: str = "", extra_css: str = "") -> str:
    """A self-contained page in the app theme: no external scripts, fonts or images."""
    css = PAGE_CSS % THEME + extra_css
    policy = "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:"
    return (
        "<!doctype html>\n<html lang=\"it\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        f"<meta http-equiv=\"Content-Security-Policy\" content=\"{policy}\">\n"
        f"<title>{esc(title)} · ZibaldOne</title>\n<style>{css}</style>\n</head>\n<body>\n"
        f"<header><h1>{esc(title)}<small>{esc(subtitle)}</small></h1></header>\n"
        f"<main>\n{body}\n</main>\n" + (f"<script>\n{script}\n</script>\n" if script else "") + "</body>\n</html>\n"
    )


GRAPH_CSS = """
#stage{position:relative;padding:0;overflow:hidden}
#graph{display:block;width:100%%;height:auto;aspect-ratio:1/1;max-height:78vh;touch-action:none;cursor:grab;background:%(background)s;border-radius:10px}
#graph.dragging{cursor:grabbing}
.edge{stroke:%(accent)s;stroke-opacity:.28}
.edge.wiki{stroke-dasharray:4 3}
.edge.shared_tag,.edge.tag,.edge.template{stroke:%(muted)s;stroke-opacity:.22;stroke-dasharray:1 3}
.edge.on{stroke-opacity:.95}
.node{stroke:%(background)s;stroke-width:1.5}
.node.missing{fill:none;stroke:%(muted)s;stroke-dasharray:2 2}
.node:hover,.node:focus,.node.on{stroke:%(text)s;outline:none}
.label{fill:%(text)s;font-size:11px;paint-order:stroke;stroke:%(background)s;stroke-width:3px;pointer-events:none}
#tip{position:absolute;pointer-events:none;max-width:260px;font-size:13px}
#tools{position:absolute;right:10px;top:10px;display:flex;gap:6px}
"""

GRAPH_SCRIPT = r"""
(function () {
  var svg = document.getElementById('graph'), tip = document.getElementById('tip'), stage = document.getElementById('stage');
  var full = {x: 0, y: 0, w: 1000, h: 1000}, view = {x: 0, y: 0, w: 1000, h: 1000};
  function apply() { svg.setAttribute('viewBox', view.x + ' ' + view.y + ' ' + view.w + ' ' + view.h); }
  function point(event) {
    var box = svg.getBoundingClientRect();
    return {x: view.x + (event.clientX - box.left) / box.width * view.w, y: view.y + (event.clientY - box.top) / box.height * view.h};
  }
  function zoom(factor, center) {
    var w = Math.min(4000, Math.max(40, view.w * factor)), scale = w / view.w;
    center = center || {x: view.x + view.w / 2, y: view.y + view.h / 2};
    view = {x: center.x - (center.x - view.x) * scale, y: center.y - (center.y - view.y) * scale, w: w, h: view.h * scale};
    apply();
  }
  svg.addEventListener('wheel', function (event) { event.preventDefault(); zoom(event.deltaY > 0 ? 1.15 : 1 / 1.15, point(event)); }, {passive: false});
  var drag = null;
  svg.addEventListener('pointerdown', function (event) { drag = {x: event.clientX, y: event.clientY, view: view}; svg.classList.add('dragging'); svg.setPointerCapture(event.pointerId); });
  svg.addEventListener('pointermove', function (event) {
    if (!drag) return;
    var box = svg.getBoundingClientRect();
    view = {x: drag.view.x - (event.clientX - drag.x) / box.width * view.w, y: drag.view.y - (event.clientY - drag.y) / box.height * view.h, w: view.w, h: view.h};
    apply();
  });
  function stop() { drag = null; svg.classList.remove('dragging'); }
  svg.addEventListener('pointerup', stop);
  svg.addEventListener('pointercancel', stop);
  document.getElementById('zoom-in').addEventListener('click', function () { zoom(1 / 1.3); });
  document.getElementById('zoom-out').addEventListener('click', function () { zoom(1.3); });
  document.getElementById('zoom-reset').addEventListener('click', function () { view = {x: full.x, y: full.y, w: full.w, h: full.h}; apply(); });
  var edges = Array.prototype.slice.call(svg.querySelectorAll('.edge'));
  function light(node, on) {
    var id = node.getAttribute('data-i');
    node.classList.toggle('on', on);
    edges.forEach(function (edge) { if (edge.getAttribute('data-s') === id || edge.getAttribute('data-t') === id) edge.classList.toggle('on', on); });
  }
  function show(node, event) {
    tip.textContent = '';
    var strong = document.createElement('strong');
    strong.textContent = node.getAttribute('data-label');
    tip.appendChild(strong);
    var meta = document.createElement('div');
    meta.className = 'muted';
    meta.textContent = node.getAttribute('data-meta');
    tip.appendChild(meta);
    var box = stage.getBoundingClientRect(), at = event && event.clientX !== undefined ? event : node.getBoundingClientRect();
    var left = (at.clientX !== undefined ? at.clientX : at.left) - box.left + 14, top = (at.clientY !== undefined ? at.clientY : at.top) - box.top + 14;
    tip.style.left = Math.min(left, box.width - 270) + 'px';
    tip.style.top = top + 'px';
    tip.hidden = false;
  }
  Array.prototype.forEach.call(svg.querySelectorAll('.node'), function (node) {
    node.addEventListener('pointerenter', function (event) { light(node, true); show(node, event); });
    node.addEventListener('pointermove', function (event) { show(node, event); });
    node.addEventListener('pointerleave', function () { light(node, false); tip.hidden = true; });
    node.addEventListener('focus', function () { light(node, true); show(node); });
    node.addEventListener('blur', function () { light(node, false); tip.hidden = true; });
  });
})();
"""

KIND_LABELS = {NODE_TAG: "etichetta", NODE_TEMPLATE: "modello", NODE_MISSING: "voce che non c'è ancora"}


def render_html(graph: Graph, title: str = "Rizoma", subtitle: str = "il grafo dei collegamenti") -> str:
    """One self-contained HTML file: inline SVG, a little inline JS for labels, zoom and pan."""
    size, margin = 1000.0, 40.0
    position = {node.id: (margin + node.x * (size - 2 * margin), margin + node.y * (size - 2 * margin)) for node in graph.nodes}
    number = {node.id: index for index, node in enumerate(graph.nodes)}
    names = {slug: name for slug, name, _ in graph.legend}
    lines = []
    for edge in graph.edges:
        if edge.source not in position or edge.target not in position:
            continue
        (x1, y1), (x2, y2) = position[edge.source], position[edge.target]
        width = 0.8 + 0.6 * min(edge.weight, 4)
        lines.append(
            f'<line class="edge {esc(edge.kind)}" data-s="{number[edge.source]}" data-t="{number[edge.target]}" '
            f'x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke-width="{width:.1f}"/>'
        )
    shown_labels = {node_id for node_id, _, _ in graph.facts.hubs[:12]}
    if len(graph.nodes) <= 60:
        shown_labels = {node.id for node in graph.nodes}
    circles, labels = [], []
    for node in graph.nodes:
        x, y = position[node.id]
        radius = min(16.0, 4.0 + 1.6 * math.sqrt(node.degree))
        meta = KIND_LABELS.get(node.kind) or " · ".join(part for part in (names.get(node.template, node.template), node.day) if part)
        meta += f" · {node.degree} collegamenti" if node.degree != 1 else " · 1 collegamento"
        fill = "none" if node.kind == NODE_MISSING else esc(node.color)
        circles.append(
            f'<circle class="node {esc(node.kind)}" tabindex="0" data-i="{number[node.id]}" data-label="{esc(node.label)}" data-meta="{esc(meta)}" '
            f'cx="{x:.1f}" cy="{y:.1f}" r="{radius:.1f}" fill="{fill}"><title>{esc(node.label)}</title></circle>'
        )
        if node.id in shown_labels:
            labels.append(f'<text class="label" x="{x + radius + 3:.1f}" y="{y + 4:.1f}">{esc(node.label[:40])}</text>')
    facts = graph.facts
    legend = "".join(f'<li><span class="swatch" style="background:{esc(color)}"></span>{esc(name)}</li>' for _, name, color in graph.legend)
    hubs = "".join(f"<li>{esc(label)} <span class=\"muted\">({degree})</span></li>" for _, label, degree in facts.hubs[:8])
    summary = (
        f"{facts.entries} voci · {facts.edges} collegamenti · {facts.components} gruppi"
        f" · {len(facts.isolated)} voci senza collegamenti" + (f" · {facts.unresolved} [[titoli]] ancora senza voce" if facts.unresolved else "")
    )
    body = (
        '<div class="grid">\n'
        '<section id="stage" class="panel">\n'
        f'<svg id="graph" viewBox="0 0 1000 1000" role="img" aria-label="{esc(summary)}" xmlns="http://www.w3.org/2000/svg">'
        f'<g>{"".join(lines)}</g><g>{"".join(circles)}</g><g>{"".join(labels)}</g></svg>\n'
        '<div id="tools"><button id="zoom-in" type="button" aria-label="Ingrandisci">+</button>'
        '<button id="zoom-out" type="button" aria-label="Rimpicciolisci">−</button>'
        '<button id="zoom-reset" type="button">Tutto</button></div>\n'
        '<div id="tip" class="panel" hidden></div>\n'
        "</section>\n"
        '<aside class="panel">\n'
        f'<h2>In breve</h2><p>{esc(summary)}</p>\n'
        + (f"<h2>Modelli</h2><ul>{legend}</ul>\n" if legend else "")
        + (f"<h2>Le più collegate</h2><ul>{hubs}</ul>\n" if hubs else "")
        + '<p class="muted">Rotella o +/− per lo zoom, trascina per spostarti, passa sopra un punto per il titolo.</p>\n'
        "</aside>\n</div>"
    )
    return html_page(title, subtitle, body, GRAPH_SCRIPT, GRAPH_CSS % THEME)
