import json
import math
import re

import pytest

from zibaldone.core.graph import (
    PALETTE,
    GraphFilters,
    build_graph,
    force_layout,
    graph_from_store,
    render_html,
    template_colors,
)
from zibaldone.core.links import LinkRecord
from zibaldone.core.packs import apply_install, find_builtin_pack, plan_install
from zibaldone.core.templates import BlockSpec, Entry, Template
from zibaldone.storage.database import Store


@pytest.fixture
def store(tmp_path):
    with Store.open(tmp_path) as opened:
        for name in ("diario", "persone"):
            apply_install(plan_install(find_builtin_pack(name), opened), opened)
        yield opened


@pytest.fixture
def people(store):
    marco = store.add_entry("persona", {"nome": "Marco"}, day="2026-01-01")
    lucia = store.add_entry("persona", {"nome": "Lucia"}, day="2026-01-01")
    dinner = store.add_entry("incontro", {"titolo": "Cena", "con": [marco.id, lucia.id], "cosa": "Con [[Marco]]"}, day="2026-10-01")
    walk = store.add_entry("incontro", {"titolo": "Passeggiata", "con": [lucia.id]}, day="2026-10-05")
    note = store.add_entry("riflessione", {"titolo": "Solo", "testo": "Nessun collegamento, ma [[Giulia]]", "etichette": ["mare"]}, day="2026-10-06")
    return {"marco": marco, "lucia": lucia, "dinner": dinner, "walk": walk, "note": note}


def ids(graph) -> set:
    return {node.id for node in graph.nodes}


def test_nodes_edges_and_facts(store, people) -> None:
    graph = graph_from_store(store)
    assert ids(graph) == {entry.id for entry in people.values()}
    dinner_marco = [edge for edge in graph.edges if {edge.source, edge.target} == {people["dinner"].id, people["marco"].id}]
    assert len(dinner_marco) == 1 and dinner_marco[0].weight == 2 and dinner_marco[0].kind == "block"
    assert len(graph.edges) == 3
    facts = graph.facts
    assert (facts.entries, facts.edges, facts.components, facts.largest_component) == (5, 3, 2, 4)
    assert [hub[1:] for hub in facts.hubs] == [("Cena", 2), ("Lucia", 2), ("Marco", 1), ("Passeggiata", 1)]
    assert facts.isolated == [(people["note"].id, "Solo")]
    assert facts.unresolved == 1
    for node in graph.nodes:
        assert 0.0 <= node.x <= 1.0 and 0.0 <= node.y <= 1.0
        assert node.color in PALETTE
    assert {slug for slug, _, _ in graph.legend} == {"persona", "incontro", "riflessione"}


def test_layout_is_deterministic_and_plain_data(store, people) -> None:
    first, second = graph_from_store(store), graph_from_store(store)
    assert [(node.id, node.x, node.y) for node in first.nodes] == [(node.id, node.x, node.y) for node in second.nodes]
    data = json.loads(first.to_json())
    assert set(data) == {"format", "nodes", "edges", "facts", "legend"}
    assert {"id", "kind", "label", "color", "x", "y", "degree", "component"} <= set(data["nodes"][0])
    linked = [node for node in first.nodes if node.degree]
    assert len({(node.x, node.y) for node in linked}) == len(linked)


def test_filters(store, people) -> None:
    only_meetings = graph_from_store(store, GraphFilters(templates=("incontro",)))
    assert ids(only_meetings) == {people["dinner"].id, people["walk"].id} and only_meetings.edges == []
    by_day = graph_from_store(store, GraphFilters(since="2026-10-02", until="2026-10-31"))
    assert ids(by_day) == {people["walk"].id, people["note"].id}
    by_tag = graph_from_store(store, GraphFilters(tag="#Mare"))
    assert ids(by_tag) == {people["note"].id}
    hidden = graph_from_store(store, GraphFilters(isolated=False))
    assert people["note"].id not in ids(hidden) and hidden.facts.isolated == [(people["note"].id, "Solo")]


def test_around_one_entry_with_depth(store, people) -> None:
    near = graph_from_store(store, GraphFilters(around=people["marco"].id[:6], depth=1))
    assert ids(near) == {people["marco"].id, people["dinner"].id}
    wider = graph_from_store(store, GraphFilters(around=people["marco"].id, depth=2))
    assert ids(wider) == {people["marco"].id, people["dinner"].id, people["lucia"].id}
    alone = graph_from_store(store, GraphFilters(around=people["note"].id, depth=3))
    assert ids(alone) == {people["note"].id}


def test_optional_nodes_and_edges(store, people) -> None:
    store.add_entry("riflessione", {"titolo": "Altro mare", "testo": "…", "etichette": ["mare"]}, day="2026-10-07")
    tags = graph_from_store(store, GraphFilters(tag_nodes=True))
    tag_node = next(node for node in tags.nodes if node.kind == "tag")
    assert (tag_node.id, tag_node.label, tag_node.degree) == ("tag:mare", "#mare", 2)
    templates = graph_from_store(store, GraphFilters(template_nodes=True))
    assert sum(1 for node in templates.nodes if node.kind == "template") == 3
    assert templates.facts.isolated == []
    shared = graph_from_store(store, GraphFilters(shared_tags=True))
    assert [(edge.kind, edge.label) for edge in shared.edges if edge.kind == "shared_tag"] == [("shared_tag", "mare")]
    ghosts = graph_from_store(store, GraphFilters(unresolved=True))
    ghost = next(node for node in ghosts.nodes if node.kind == "missing")
    assert ghost.label == "Giulia" and ghost.degree == 1


def test_shared_tags_chain_big_groups() -> None:
    template = Template("nota", "Nota", [BlockSpec("titolo", "text", "Titolo"), BlockSpec("etichette", "tags", "Etichette")])
    entries = [Entry(f"{number:032x}", "nota", {"titolo": f"N{number}"}, f"2026-01-{number + 1:02d}", "t", "t") for number in range(10)]
    tags = {entry.id: ["tutti"] for entry in entries}
    graph = build_graph(entries, {"nota": template}, [], tags, GraphFilters(shared_tags=True))
    assert len(graph.edges) == 9 and graph.facts.components == 1  # a chain by date, not 45 edges


def test_force_layout_edge_cases() -> None:
    assert force_layout([], []) == []
    assert force_layout(["a"], []) == [(0.5, 0.5)]
    pair = force_layout(["a", "b"], [(0, 1, 1)], iterations=50)
    assert math.dist(*pair) > 0
    many = [f"n{number}" for number in range(120)]
    edges = [(number, (number * 7 + 3) % 120, 1) for number in range(120)]
    first, second = force_layout(many, edges, iterations=40), force_layout(many, edges, iterations=40)
    assert first == second
    assert all(math.isfinite(x) and math.isfinite(y) for x, y in first)


def test_template_colors_are_stable() -> None:
    assert template_colors(["sera", "libro", "sera"]) == {"libro": PALETTE[0], "sera": PALETTE[1]}
    assert len(set(template_colors([f"t{number}" for number in range(7)]).values())) == 7


def test_html_is_self_contained_and_escaped(store) -> None:
    evil = store.add_entry("persona", {"nome": '<script>alert("x")</script> & "Tom"'}, day="2026-01-01")
    store.add_entry("incontro", {"titolo": "<img src=x onerror=alert(1)>", "con": [evil.id]}, day="2026-10-01")
    page = render_html(graph_from_store(store))
    assert "<script>alert" not in page and "<img src" not in page
    assert "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt; &amp; &quot;Tom&quot;" in page
    assert len(re.findall(r"<script>", page)) == 1  # only the inline script of the page itself
    for forbidden in ("<script src", "<link", "@import", "url(", "https://", "@font-face"):
        assert forbidden not in page
    assert re.findall(r"https?://[^\"' ]+", page) == ["http://www.w3.org/2000/svg"]
    for color in ("#0D0E15", "#141521", "#E6F7FF", "#00E5FF"):
        assert color in page
    assert "Content-Security-Policy" in page and 'lang="it"' in page


def test_unknown_center_is_refused(store, people) -> None:
    with pytest.raises(Exception):
        graph_from_store(store, GraphFilters(around="ffff"))
