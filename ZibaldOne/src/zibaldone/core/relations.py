"""Legami (0.2.2): relations between people, the family tree, who knows whom.

A person (Agorà 1.3.0) links other people in four blocks: Genitori, Fratelli e
sorelle, Colleghi, Conosce (`RELATION_BLOCKS` in `core/people.py`). Each link
reads both ways: if Luca has Anna among his parents, Anna has Luca among her
children. People seen in the same Simposio know each other too.

The family tree puts people in generations around you: base roles say where
(the mother one above, a grandfather two above, a son one below), parent and
sibling links carry it on. The strength of a bond, 0 to 10, comes from the
contacts with someone, each counting less as it gets older, and, when the
meetings have an Umore, from how they went.

Pure functions over `Person` objects, with `today` always passed in; the one
helper that writes goes through a Store.
"""

from collections import deque
from dataclasses import dataclass
from datetime import date
from itertools import combinations
from typing import Any, Deque, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from zibaldone.core.areas import AREA_BY_KEY, DEFAULT_COLOR
from zibaldone.core.graph import NODE_ENTRY, Graph, GraphEdge, GraphFacts, GraphNode, SEED, _components, _place
from zibaldone.core.people import RELATION_BLOCKS, RHYTHM_CONTACTS, PeopleError, Person

PARENT, CHILD, SIBLING, COLLEAGUE, KNOWS = "genitore", "figlio", "fratello", "collega", "conosce"
TIE_ORDER = (PARENT, CHILD, SIBLING, COLLEAGUE, KNOWS)
INVERSE = {PARENT: CHILD, CHILD: PARENT, SIBLING: SIBLING, COLLEAGUE: COLLEAGUE, KNOWS: KNOWS}
TIE_LABELS = {PARENT: "Genitori", CHILD: "Figli", SIBLING: "Fratelli e sorelle", COLLEAGUE: "Colleghi", KNOWS: "Conosce"}
TIE_HOW = {PARENT: "genitore", CHILD: "figlio o figlia", SIBLING: "fratello o sorella", COLLEAGUE: "collega", KNOWS: "si conoscono"}
FAMILY_TIES = (PARENT, CHILD, SIBLING)
# Words for `zbone persona lega A <parola> B` ("A è <parola> di B").
TIE_WORDS = {
    "genitore": PARENT, "madre": PARENT, "padre": PARENT,
    "figlio": CHILD, "figlia": CHILD,
    "fratello": SIBLING, "sorella": SIBLING,
    "collega": COLLEAGUE,
    "conosce": KNOWS, "conoscente": KNOWS,
}
BLOCK_OF = {PARENT: "genitori", SIBLING: "fratelli", COLLEAGUE: "colleghi", KNOWS: "conosce"}
assert set(BLOCK_OF.values()) == set(RELATION_BLOCKS)

YOU = "Tu"
# Where base roles (relative to you) sit in the tree: 0 is your generation.
ROLE_GENERATIONS: Dict[str, int] = {
    "nonno": -2, "nonna": -2,
    "madre": -1, "padre": -1, "genitore": -1, "zio": -1, "zia": -1, "suocero": -1, "suocera": -1,
    "fratello": 0, "sorella": 0, "partner": 0, "marito": 0, "moglie": 0, "cugino": 0, "cugina": 0, "cognato": 0, "cognata": 0,
    "figlio": 1, "figlia": 1,
}  # "nipote" is left out: in Italian it is both a grandchild and a niece or nephew
PARENT_ROLES = ("madre", "padre", "genitore")
LEVEL_LABELS = {-3: "Bisnonni", -2: "Nonni", -1: "Genitori e zii", 0: "Tu, fratelli e cugini", 1: "Figli e nipoti", 2: "Figli dei figli"}
STEP = {PARENT: -1, CHILD: 1, SIBLING: 0}

STRENGTH_HALF_LIFE = 90  # days: a contact three months ago counts half as much as one today
STRENGTH_FULL = 8.0  # that much of fresh contacts is a full bond: about one every two weeks, kept up
STRENGTH_WORDS = ((8, "molto stretto"), (5, "stretto"), (2, "saltuario"), (0, "lontano"))


def and_list(names: Sequence[str]) -> str:
    """'Anna', 'Anna e Paolo', 'Anna, Paolo e Pietro'."""
    names = list(names)
    if len(names) < 2:
        return names[0] if names else ""
    return ", ".join(names[:-1]) + " e " + names[-1]


def _key(text: str) -> str:
    return " ".join(str(text).strip().lower().split())


# * — ties —


@dataclass(frozen=True)
class Tie:
    other: str  # person id
    kind: str  # what `other` is to the person: PARENT, CHILD …


def ties_of(people: Sequence[Person]) -> Dict[str, List[Tie]]:
    """Every person's ties, each link read both ways, closest kinds first."""
    ids = {person.id for person in people}
    names = {person.id: person.name.casefold() for person in people}
    found: Dict[str, Set[Tie]] = {}
    for person in people:
        for key, refs in person.relations.items():
            kind = RELATION_BLOCKS[key]
            for ref in refs:
                if ref in ids and ref != person.id:
                    found.setdefault(person.id, set()).add(Tie(ref, kind))
                    found.setdefault(ref, set()).add(Tie(person.id, INVERSE[kind]))
    return {
        person_id: sorted(ties, key=lambda tie: (TIE_ORDER.index(tie.kind), names[tie.other], tie.other))
        for person_id, ties in found.items()
    }


def together_counts(people: Iterable[Person]) -> Dict[Tuple[str, str], int]:
    """How many Simposi each pair of people shared, keyed by the sorted pair of ids."""
    by_meeting: Dict[str, Set[str]] = {}
    for person in people:
        for contact in person.contacts:
            by_meeting.setdefault(contact.entry_id, set()).add(person.id)
    counts: Dict[Tuple[str, str], int] = {}
    for members in by_meeting.values():
        for pair in combinations(sorted(members), 2):
            counts[pair] = counts.get(pair, 0) + 1
    return counts


def _pair(a: str, b: str) -> Tuple[str, str]:
    return (a, b) if a < b else (b, a)


# * — the network: who knows whom —


@dataclass(frozen=True)
class Connection:
    person: Person
    kinds: Tuple[str, ...]  # what they are to the center
    together: int  # Simposi shared with the center
    in_common: Tuple[Person, ...]  # people both of them know

    @property
    def how(self) -> str:
        """'genitore', 'collega, 2 incontri insieme'."""
        parts = [TIE_HOW[kind] for kind in self.kinds]
        if self.together:
            parts.append("1 incontro insieme" if self.together == 1 else f"{self.together} incontri insieme")
        return ", ".join(parts)

    @property
    def common_line(self) -> str:
        count = len(self.in_common)
        return "" if not count else "1 in comune" if count == 1 else f"{count} in comune"


class Network:
    """People and who knows whom among them (ties and shared Simposi)."""

    def __init__(self, people: Sequence[Person]) -> None:
        self.people = list(people)
        self.by_id = {person.id: person for person in self.people}
        self.ties = ties_of(self.people)
        self.together = together_counts(self.people)
        self._near: Dict[str, Set[str]] = {person.id: {tie.other for tie in self.ties.get(person.id, [])} for person in self.people}
        for a, b in self.together:
            self._near[a].add(b)
            self._near[b].add(a)

    def neighbours(self, person_id: str) -> Set[str]:
        return set(self._near.get(person_id, ()))

    def _sorted(self, ids: Iterable[str]) -> Tuple[Person, ...]:
        return tuple(sorted((self.by_id[i] for i in ids), key=lambda person: (person.name.casefold(), person.id)))

    def in_common(self, a: str, b: str) -> Tuple[Person, ...]:
        """People both `a` and `b` know."""
        return self._sorted((self.neighbours(a) & self.neighbours(b)) - {a, b})

    def connections(self, person_id: str) -> List[Connection]:
        """Who the person knows: family first, then colleagues, acquaintances and who they met with you."""
        kinds: Dict[str, List[str]] = {}
        for tie in self.ties.get(person_id, []):
            kinds.setdefault(tie.other, []).append(tie.kind)
        found = [
            Connection(self.by_id[other], tuple(kinds.get(other, ())), self.together.get(_pair(person_id, other), 0), self.in_common(person_id, other))
            for other in self.neighbours(person_id)
        ]
        return sorted(found, key=lambda link: (min((TIE_ORDER.index(kind) for kind in link.kinds), default=len(TIE_ORDER)), -link.together, link.person.name.casefold()))

    def pairs(self) -> List[Tuple[str, str, Tuple[str, ...], int]]:
        """(a, b, kinds of b to a, Simposi together) for every connected pair, a < b."""
        keys = {_pair(person.id, tie.other) for person in self.people for tie in self.ties.get(person.id, [])} | set(self.together)
        result = []
        for a, b in sorted(keys):
            kinds = tuple(tie.kind for tie in self.ties.get(a, []) if tie.other == b)
            result.append((a, b, kinds, self.together.get((a, b), 0)))
        return result


def network(people: Sequence[Person], area: Optional[str] = None) -> Network:
    """The network of everyone, or only of the people in one area."""
    return Network([person for person in people if area is None or area in person.areas])


def area_color(area: str) -> str:
    found = AREA_BY_KEY.get(area)
    return found.color if found else DEFAULT_COLOR


def edge_kind(kinds: Sequence[str]) -> str:
    """The graph edge kind: 'famiglia', 'lavoro', 'conosce' or 'incontri' (only Simposi together)."""
    if any(kind in FAMILY_TIES for kind in kinds):
        return "famiglia"
    if COLLEAGUE in kinds:
        return "lavoro"
    return "conosce" if kinds else "incontri"


def network_graph(net: Network, seed: int = SEED) -> Graph:
    """The network as a Rizoma graph, laid out the same way, nodes coloured by area."""
    nodes = [
        GraphNode(person.id, NODE_ENTRY, person.name, area_color(person.main_area), template=person.entry.template, day=person.entry.day)
        for person in net.people
    ]
    edges = []
    for a, b, kinds, together in net.pairs():
        how = Connection(net.by_id[b], kinds, together, ()).how
        edges.append(GraphEdge(a, b, edge_kind(kinds), weight=len(kinds) + together, label=how))
    degree = {node.id: len(net.neighbours(node.id)) for node in nodes}
    for node in nodes:
        node.degree = degree[node.id]
    _place(nodes, edges, seed, None)
    groups = _components([node.id for node in nodes], [(edge.source, edge.target) for edge in edges])
    hubs = sorted(((node.id, node.label, node.degree) for node in nodes), key=lambda hub: (-hub[2], hub[1].casefold()))
    facts = GraphFacts(
        entries=len(nodes),
        nodes=len(nodes),
        edges=len(edges),
        components=len(groups),
        largest_component=max((len(group) for group in groups), default=0),
        hubs=hubs[:10],
        isolated=[(node.id, node.label) for node in nodes if not node.degree],
        unresolved=0,
    )
    areas = []
    for person in net.people:
        if person.main_area and person.main_area not in areas:
            areas.append(person.main_area)
    legend = [(area, AREA_BY_KEY[area].label, area_color(area)) for area in AREA_BY_KEY if area in areas]
    return Graph(nodes, edges, facts, legend)


# * — the strength of a bond —


def strength(person: Person, today: date) -> Optional[int]:
    """0–10: every contact day counts, less as it gets older; the Umore of the last meetings adds a little.

    None when you never heard from them.
    """
    if not person.contacts:
        return None
    days = {contact.day for contact in person.contacts}
    fresh = sum(0.5 ** (max(0, (today - day).days) / STRENGTH_HALF_LIFE) for day in days)
    often = min(1.0, fresh / STRENGTH_FULL)
    moods = [contact.mood for contact in person.contacts[:RHYTHM_CONTACTS] if contact.mood is not None]
    score = often if not moods else 0.8 * often + 0.2 * (sum(moods) / len(moods) - 1) / 4
    return round(10 * score)


def strength_word(score: int) -> str:
    return next(word for limit, word in STRENGTH_WORDS if score >= limit)


def strength_line(person: Person, today: date) -> str:
    """'forza del legame 7/10 (stretto)', or '' before the first contact."""
    score = strength(person, today)
    return "" if score is None else f"forza del legame {score}/10 ({strength_word(score)})"


def strongest(people: Iterable[Person], today: date) -> List[Tuple[Person, int]]:
    """People by the strength of the bond, strongest first (never heard ones left out)."""
    scored = [(person, strength(person, today)) for person in people]
    return sorted(((person, score) for person, score in scored if score is not None), key=lambda item: (-item[1], item[0].name.casefold()))


# * — the family tree —


def role_generation(person: Person) -> Optional[int]:
    """Where the person's first family role puts them around you, or None."""
    for role in person.roles:
        level = ROLE_GENERATIONS.get(_key(role))
        if level is not None:
            return level
    return None


@dataclass(frozen=True)
class TreeMember:
    person: Optional[Person]  # None: you
    level: int
    parents: Tuple[str, ...]  # names

    @property
    def name(self) -> str:
        return self.person.name if self.person else YOU

    @property
    def caption(self) -> str:
        """'madre · genitori: Pietro e Rosa'."""
        roles = ", ".join(self.person.roles) if self.person else ""
        parents = f"genitori: {and_list(self.parents)}" if self.parents else ""
        return " · ".join(part for part in (roles, parents) if part)


@dataclass
class Generation:
    level: int
    label: str
    members: List[TreeMember]


def generation_label(level: int) -> str:
    if level in LEVEL_LABELS:
        return LEVEL_LABELS[level]
    return f"{-level} generazioni prima di te" if level < 0 else f"{level} generazioni dopo di te"


def family_tree(people: Sequence[Person]) -> List[Generation]:
    """The family by generation, the oldest first; you are in it when a role says where they stand from you."""
    ties = ties_of(people)
    family = {person.id: [tie for tie in ties.get(person.id, []) if tie.kind in FAMILY_TIES] for person in people}
    members = [person for person in people if "famiglia" in person.areas or role_generation(person) is not None or family[person.id]]
    level: Dict[str, int] = {}
    queue: Deque[str] = deque()
    for person in members:
        found = role_generation(person)
        if found is not None:
            level[person.id] = found
            queue.append(person.id)
    anchored = bool(level)

    def spread() -> None:
        while queue:
            current = queue.popleft()
            for tie in family[current]:
                if tie.other not in level:
                    level[tie.other] = level[current] + STEP[tie.kind]
                    queue.append(tie.other)

    spread()
    for person in members:
        if person.id not in level:  # nothing says where: your generation, then their links carry it on
            level[person.id] = 0
            queue.append(person.id)
            spread()
    if not members:
        return []
    by_id = {person.id: person for person in people}
    rows: Dict[int, List[TreeMember]] = {}
    for person in members:
        parents = tuple(by_id[tie.other].name for tie in family[person.id] if tie.kind == PARENT)
        rows.setdefault(level[person.id], []).append(TreeMember(person, level[person.id], parents))
    for row in rows.values():
        row.sort(key=lambda member: (not member.parents, tuple(name.casefold() for name in member.parents), member.name.casefold()))
    if anchored:
        yours = tuple(person.name for person in members if any(_key(role) in PARENT_ROLES for role in person.roles))
        rows.setdefault(0, []).insert(0, TreeMember(None, 0, yours))
        return [Generation(number, generation_label(number), rows[number]) for number in sorted(rows)]
    return [Generation(number, f"Generazione {position}", rows[number]) for position, number in enumerate(sorted(rows), start=1)]


# * — writing a tie —


def tie_plan(a: Person, kind: str, b: Person) -> Tuple[Person, str, str]:
    """`a` is <kind> of `b`: (whose block changes, which block, which id goes in)."""
    if a.id == b.id:
        raise PeopleError("una persona non può essere legata a sé stessa")
    if kind == PARENT:
        return b, BLOCK_OF[PARENT], a.id
    if kind == CHILD:
        return a, BLOCK_OF[PARENT], b.id
    return b, BLOCK_OF[kind], a.id


def parse_tie(word: str) -> str:
    kind = TIE_WORDS.get(_key(word))
    if kind is None:
        raise PeopleError(f"legame sconosciuto: '{word}'. Puoi scrivere: {', '.join(TIE_WORDS)}")
    return kind


def add_tie(store: Any, a: Person, kind: str, b: Person) -> bool:
    """Write that `a` is <kind> of `b`; False when the link was already there."""
    holder, key, ref = tie_plan(a, kind, b)
    other = b if holder is a else a
    if ref in holder.relations.get(key, []) or (kind not in (PARENT, CHILD) and holder.id in other.relations.get(key, [])):
        return False
    if key == BLOCK_OF[PARENT] and holder.id in other.relations.get(key, []):
        raise PeopleError(f"{holder.name} è già genitore di {other.name}")
    template = store.get_template(holder.entry.template)
    if key not in {spec.key for spec in template.blocks if spec.type == "link"}:
        raise PeopleError(f"il modello «{template.name}» non ha i legami: aggiorna la Scuola «Agorà · Persone» (`zbone pack install persone`)")
    store.update_entry(holder.id, {key: [*holder.entry.values.get(key, []), ref]})
    return True
