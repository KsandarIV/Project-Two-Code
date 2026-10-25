"""Eudaimonia (0.2.0): the 8 life areas as a concept of the whole app.

Every template can have an area (Libro → svago, Mens sana → salute) and every
entry can have its own, which wins over the template's. A `tags` block keyed
`aree` (in "L'Altro", the person template) puts an entry in more areas at once,
and so do a person's bond and roles (0.2.1, `core/roles.py`: a mother is in
Famiglia, a colleague in Lavoro). The template's area is then only the
fallback, for entries that get no area in any other way.

For each area the app shows:

- the score over time (0–10): the area's scale in the daily check-in of the
  8 areas (Eudaimonia), plus the `punteggio` scale of any entry in the area
  (the per-area check-in, Prosoché);
- the to-dos: unticked checklist items of the area's entries;
- the goals: entries of the "Telos" template (slug `obiettivo`);
- the notes and every other entry of the area.

Pure functions over entries and templates, like `core/stats.py`; `today` is
always passed in. The few helpers that write go through a Store.
"""

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from zibaldone.core.blocks import BLOCK_TYPES, PROGRESS_STATUSES
from zibaldone.core.brand import AREAS, Mascot, mascot_for
from zibaldone.core.links import is_person_template
from zibaldone.core.roles import role_areas
from zibaldone.core.stats import Period, entry_date, number, week_of
from zibaldone.core.templates import BlockSpec, Entry, Template

AREA_TAGS_BLOCK = "aree"  # a tags block with this key lists more areas (people)
SCORE_BLOCK = "punteggio"  # a scale with this key scores the entry's own area
CHECKIN_TEMPLATE = "checkin_area"
GOAL_TEMPLATE = "obiettivo"
TODO_TEMPLATE = "da_fare"
TODO_BLOCK = "elenco"
AREAS_PACK = "zibaldone.aree"
AREAS_PACK_NAME = "aree"
WINDOW_DAYS = 30
TREND_STEP = 0.5  # on 0–10: a smaller change reads as "stabile"
CLOSED_GOALS = ("completed", "dropped")
DEFAULT_COLOR = "#00E5FF"


@dataclass(frozen=True)
class Area:
    key: str
    label: str
    covers: str  # what belongs here, in plain words
    icon: str  # Flet icon name

    @property
    def mascot(self) -> Optional[Mascot]:
        return mascot_for(self.key)

    @property
    def color(self) -> str:
        mascot = self.mascot
        return mascot.color if mascot else DEFAULT_COLOR


AREA_LIST: Tuple[Area, ...] = (
    Area("personale", "Personale", "chi sei: identità, valori, crescita, il tuo secondo cervello", "SELF_IMPROVEMENT"),
    Area("salute", "Salute", "corpo e mente: sonno, movimento, alimentazione, cure", "FAVORITE_OUTLINE"),
    Area("finanze", "Finanze", "denaro, spese, risparmi, progetti economici", "SAVINGS_OUTLINED"),
    Area("famiglia", "Famiglia", "i tuoi familiari e il tempo passato con loro", "FAMILY_RESTROOM"),
    Area("sociale", "Sociale", "amici, conoscenti, comunità", "GROUPS_OUTLINED"),
    Area("lavoro", "Lavoro", "lavoro, carriera, progetti", "WORK_OUTLINE"),
    Area("studio", "Studio", "scuola, corsi, quello che stai imparando", "SCHOOL_OUTLINED"),
    Area("svago", "Svago", "hobby, giochi, libri, film, serie, musica", "SPORTS_ESPORTS_OUTLINED"),
)
AREA_BY_KEY: Dict[str, Area] = {area.key: area for area in AREA_LIST}
assert tuple(AREA_BY_KEY) == tuple(AREAS)

# Other ways to write an area: English names (the old Journal App) and common synonyms.
ALIASES: Dict[str, str] = {
    "personal": "personale", "io": "personale", "se": "personale",
    "health": "salute", "benessere": "salute",
    "finance": "finanze", "finances": "finanze", "finanza": "finanze", "soldi": "finanze", "denaro": "finanze",
    "family": "famiglia",
    "social": "sociale", "amici": "sociale", "amicizie": "sociale",
    "work": "lavoro", "carriera": "lavoro",
    "education": "studio", "istruzione": "studio", "formazione": "studio", "scuola": "studio",
    "recreation": "svago", "hobby": "svago", "tempo libero": "svago", "divertimento": "svago",
}


def _fold(text: str) -> str:
    folded = text.lower().translate(str.maketrans("àáèéìíòóùú", "aaeeiioouu"))
    return " ".join(re.sub(r"[^a-z ]+", " ", folded).split())


def find_area(text: Any) -> Optional[str]:
    """'Salute', 'salute', 'Health' → 'salute'; anything else → None."""
    if not isinstance(text, str):
        return None
    folded = _fold(text)
    if folded in AREA_BY_KEY:
        return folded
    return ALIASES.get(folded)


def parse_area(text: str) -> str:
    """Like find_area, but an unknown area is an error with the list of the 8."""
    key = find_area(text)
    if key is None:
        raise ValueError(f"area sconosciuta: '{text}'. Le aree sono: {', '.join(AREAS)}")
    return key


def area_info(key: str) -> Area:
    return AREA_BY_KEY[parse_area(key)]


def area_label(key: str) -> str:
    area = AREA_BY_KEY.get(key)
    return area.label if area else ""


# * — which areas an entry belongs to —


def own_area(entry: Entry, template: Optional[Template]) -> str:
    """The entry's area, else its template's, else ''."""
    return entry.area or (template.area if template is not None else "")


def entry_areas(entry: Entry, template: Optional[Template]) -> List[str]:
    """Every area of the entry, the main one first.

    Its own area, then those listed in an `aree` tags block, then (people) the
    areas of its bond and roles; the template's area only when none of these
    gives one.
    """
    found: List[str] = [entry.area] if entry.area else []
    if template is None:
        return found
    for spec in template.blocks:
        if spec.type == "tags" and spec.key == AREA_TAGS_BLOCK:
            listed = {find_area(tag) for tag in entry.values.get(spec.key, [])}
            found += [key for key in AREAS if key in listed and key not in found]
    if is_person_template(template):
        found += [key for key in role_areas(entry, template) if key not in found]
    if not found:
        found += template.all_areas()
    return found


def main_area(entry: Entry, template: Optional[Template]) -> str:
    """The first of the entry's areas, '' when it has none."""
    found = entry_areas(entry, template)
    return found[0] if found else ""


def in_area(entry: Entry, template: Optional[Template], area: str) -> bool:
    return area in entry_areas(entry, template)


# * — scores (0–10) —


def _scale_area(spec: BlockSpec) -> Optional[str]:
    """The area a scale stands for by its own name (Eudaimonia: one scale per area)."""
    if spec.key in AREA_BY_KEY:
        return spec.key
    label = _fold(spec.label)
    return label if label in AREA_BY_KEY else None


def entry_scores(entry: Entry, template: Optional[Template]) -> Dict[str, float]:
    """Area → score brought to 0–10, for the scales of this entry that score an area."""
    if template is None:
        return {}
    scores: Dict[str, float] = {}
    own = own_area(entry, template)
    for spec in template.blocks:
        value = entry.values.get(spec.key)
        if spec.type != "scale" or value is None:
            continue
        area = _scale_area(spec)
        if area is None and spec.key == SCORE_BLOCK:
            area = own or None
        if area is None:
            continue
        low, high = BLOCK_TYPES["scale"].bounds(spec.options)
        scores[area] = 10.0 * (value - low) / (high - low)
    return scores


@dataclass(frozen=True)
class ScorePoint:
    start: date
    end: date
    average: Optional[float]
    count: int


def _average(values: Sequence[float]) -> Optional[float]:
    return sum(values) / len(values) if values else None


def daily_scores(entries: Iterable[Entry], templates: Mapping[str, Template], area: str) -> Dict[date, float]:
    """Average score of the area on each day that has one."""
    collected: Dict[date, List[float]] = {}
    for entry in entries:
        score = entry_scores(entry, templates.get(entry.template)).get(area)
        if score is not None:
            collected.setdefault(entry_date(entry), []).append(score)
    return {day: sum(values) / len(values) for day, values in collected.items()}


def score_series(daily: Mapping[date, float], end: date, weeks: int = 12) -> List[ScorePoint]:
    """Weekly averages of the area's score, oldest first, ending with the week of `end`."""
    last = week_of(end)
    points = []
    for back in range(weeks - 1, -1, -1):
        period = Period("week", last.start - timedelta(days=7 * back), last.end - timedelta(days=7 * back))
        values = [score for day, score in daily.items() if period.contains(day)]
        points.append(ScorePoint(period.start, period.end, _average(values), len(values)))
    return points


def score_text(score: Optional[float]) -> str:
    return "—" if score is None else f"{number(score)}/10"


# * — to-dos and goals —


@dataclass(frozen=True)
class AreaTodo:
    text: str
    entry_id: str
    block: str
    index: int
    day: date
    source: str  # the title of the entry it comes from
    template: str = ""


def _todo_key(text: str) -> str:
    return " ".join(text.lower().split())


def area_todos(entries: Iterable[Entry], templates: Mapping[str, Template], area: str) -> List[AreaTodo]:
    """Unticked checklist items of the area's entries, oldest first.

    The same text written again later counts once, with its latest state
    (ticked later means done), as in the reviews.
    """
    state: Dict[str, Tuple[bool, AreaTodo]] = {}
    ordered = sorted(entries, key=lambda entry: (entry.day, entry.created_at))  # stable: ties keep the store's order
    for entry in ordered:
        template = templates.get(entry.template)
        if template is None or not in_area(entry, template, area):
            continue
        for spec in template.blocks:
            if spec.type != "checklist":
                continue
            for index, item in enumerate(entry.values.get(spec.key, [])):
                todo = AreaTodo(item["text"], entry.id, spec.key, index, entry_date(entry), entry.title(template), template.slug)
                state[_todo_key(item["text"])] = (bool(item.get("done")), todo)
    return [todo for done, todo in state.values() if not done]


def is_goal_template(template: Optional[Template]) -> bool:
    return template is not None and (template.slug == GOAL_TEMPLATE or template.slug.startswith(GOAL_TEMPLATE + "_"))


@dataclass(frozen=True)
class AreaGoal:
    entry_id: str
    title: str
    status: str
    percent: Optional[int]
    deadline: Optional[date]
    steps_done: int
    steps_total: int
    day: date

    @property
    def active(self) -> bool:
        return self.status not in CLOSED_GOALS

    @property
    def status_label(self) -> str:
        return PROGRESS_STATUSES.get(self.status, self.status)


def goal_of(entry: Entry, template: Template) -> AreaGoal:
    status, percent, deadline = "not_started", None, None
    done = total = 0
    for spec in template.blocks:
        value = entry.values.get(spec.key)
        if value is None:
            continue
        if spec.type == "progress" and isinstance(value, dict) and status == "not_started" and percent is None:
            status = value.get("status", "not_started")
            current, top = value.get("current"), value.get("total")
            if current is not None and top:
                percent = max(0, min(100, round(100 * current / top)))
        elif spec.type == "date" and deadline is None:
            try:
                deadline = date.fromisoformat(value)
            except (TypeError, ValueError):
                pass
        elif spec.type == "checklist":
            total += len(value)
            done += sum(1 for item in value if item.get("done"))
    if percent is None and total:
        percent = round(100 * done / total)
    if status == "completed":
        percent = 100
    return AreaGoal(entry.id, entry.title(template), status, percent, deadline, done, total, entry_date(entry))


def area_goals(entries: Iterable[Entry], templates: Mapping[str, Template], area: str) -> List[AreaGoal]:
    """The area's goals: open ones first (nearest deadline first), then the closed ones."""
    goals = []
    for entry in entries:
        template = templates.get(entry.template)
        if is_goal_template(template) and in_area(entry, template, area):
            goals.append(goal_of(entry, template))
    far = date.max
    return sorted(goals, key=lambda goal: (not goal.active, goal.deadline or far, -goal.day.toordinal(), goal.title.lower()))


@dataclass(frozen=True)
class GoalLine:
    area: str
    goal: AreaGoal
    days_left: Optional[int]  # negative once the deadline is gone; None without a deadline


def goals_overview(store: Any, today: date, area: str = "") -> List[GoalLine]:
    """The goals still open, one line each under the goal's main area, nearest deadline first; those with no deadline come last."""
    key = parse_area(area) if area else ""
    templates = {template.slug: template for template in store.list_templates()}
    lines = []
    for entry in store.list_entries(newest_first=False):
        template = templates.get(entry.template)
        if not is_goal_template(template) or (key and not in_area(entry, template, key)):
            continue
        goal = goal_of(entry, template)
        if goal.active:
            lines.append(GoalLine(key or main_area(entry, template), goal, (goal.deadline - today).days if goal.deadline else None))
    far = date.max
    return sorted(lines, key=lambda line: (line.goal.deadline or far, line.goal.title.casefold(), line.goal.entry_id))


# * — overview and detail —


@dataclass
class AreaSummary:
    area: Area
    latest: Optional[float] = None
    latest_day: Optional[date] = None
    average: Optional[float] = None  # last WINDOW_DAYS days
    previous: Optional[float] = None  # the WINDOW_DAYS days before
    entries: int = 0  # entries of the area in the last WINDOW_DAYS days
    total: int = 0  # entries of the area, ever
    todos: int = 0
    goals: int = 0  # open goals

    @property
    def trend(self) -> Optional[str]:
        """'su', 'giù' or 'stabile' (average against the previous window), or None."""
        if self.average is None or self.previous is None:
            return None
        delta = self.average - self.previous
        if abs(delta) < TREND_STEP:
            return "stabile"
        return "su" if delta > 0 else "giù"

    @property
    def fraction(self) -> Optional[float]:
        score = self.latest if self.latest is not None else self.average
        return None if score is None else max(0.0, min(1.0, score / 10))

    @property
    def counts_label(self) -> str:
        parts = []
        if self.todos:
            parts.append("1 da fare" if self.todos == 1 else f"{self.todos} da fare")
        if self.goals:
            parts.append("1 obiettivo" if self.goals == 1 else f"{self.goals} obiettivi")
        if self.entries == 0:
            parts.append("nessuna voce in 30 giorni")
        else:
            parts.append("1 voce in 30 giorni" if self.entries == 1 else f"{self.entries} voci in 30 giorni")
        return " · ".join(parts)


def _summary(area: Area, entries: Sequence[Entry], templates: Mapping[str, Template], today: date) -> AreaSummary:
    mine = [entry for entry in entries if in_area(entry, templates.get(entry.template), area.key)]
    daily = daily_scores(entries, templates, area.key)
    summary = AreaSummary(area)
    past = {day: score for day, score in daily.items() if day <= today}
    if past:
        summary.latest_day = max(past)
        summary.latest = past[summary.latest_day]
    start = today - timedelta(days=WINDOW_DAYS - 1)
    before = start - timedelta(days=WINDOW_DAYS)
    summary.average = _average([score for day, score in past.items() if day >= start])
    summary.previous = _average([score for day, score in past.items() if before <= day < start])
    summary.entries = sum(1 for entry in mine if start <= entry_date(entry) <= today)
    summary.total = len(mine)
    summary.todos = len(area_todos(mine, templates, area.key))
    summary.goals = sum(1 for goal in area_goals(mine, templates, area.key) if goal.active)
    return summary


def area_overview(entries: Sequence[Entry], templates: Mapping[str, Template], today: date) -> List[AreaSummary]:
    """One summary per area, in the usual order."""
    return [_summary(area, entries, templates, today) for area in AREA_LIST]


@dataclass
class AreaDetail:
    summary: AreaSummary
    series: List[ScorePoint]
    todos: List[AreaTodo]
    goals: List[AreaGoal]
    recent: List[Entry]  # newest first
    checkins: int
    templates: List[str] = field(default_factory=list)  # slugs of the templates whose area this is

    @property
    def area(self) -> Area:
        return self.summary.area


def area_entries(entries: Iterable[Entry], templates: Mapping[str, Template], area: str) -> List[Entry]:
    """The area's entries, newest first."""
    mine = [entry for entry in entries if in_area(entry, templates.get(entry.template), area)]
    return list(reversed(sorted(mine, key=lambda entry: (entry.day, entry.created_at))))


def area_detail(entries: Sequence[Entry], templates: Mapping[str, Template], key: str, today: date, weeks: int = 12, recent: int = 12) -> AreaDetail:
    area = area_info(key)
    mine = area_entries(entries, templates, area.key)
    daily = daily_scores(entries, templates, area.key)
    checkins = sum(1 for entry in mine if entry_scores(entry, templates.get(entry.template)).get(area.key) is not None)
    return AreaDetail(
        summary=_summary(area, entries, templates, today),
        series=score_series({day: score for day, score in daily.items() if day <= today}, today, weeks),
        todos=area_todos(entries, templates, area.key),  # oldest first, as the store gives them
        goals=area_goals(entries, templates, area.key),
        recent=mine[:recent],
        checkins=checkins,
        templates=sorted(slug for slug, template in templates.items() if area.key in template.all_areas()),
    )


# * — coming soon: what each area will get in the next versions —


@dataclass(frozen=True)
class Upcoming:
    """A feature announced on the area pages before it exists ("In arrivo")."""

    title: str
    teaser: str
    version: str  # "0.2.6", or "dopo la 1.0"
    areas: Tuple[str, ...] = ()  # empty: shown on the overview of all the areas

    @property
    def when(self) -> str:
        return self.version if self.version[:1].isalpha() else f"versione {self.version}"


# Remove an item when its version ships: a test checks that none is older than the app.
UPCOMING: Tuple[Upcoming, ...] = (
    Upcoming("Sblocco con l'impronta", "aprire i segreti con l'impronta o il volto, quando l'app potrà chiederli al telefono", "più avanti", ("personale",)),
    Upcoming("Maieutica", "un'IA che ti fa domande sulle tue aree («le mie azioni riflettono i miei valori?»), sempre dietro il Velo d'ignoranza", "dopo la 1.0"),
)


def upcoming_for(area: str = "") -> List[Upcoming]:
    """What is coming for one area, or (area='') the items for all the areas."""
    if not area:
        return [item for item in UPCOMING if not item.areas]
    key = parse_area(area)
    return [item for item in UPCOMING if key in item.areas]


# * — writing through a Store —


class AreaError(ValueError):
    """An area action cannot run (for example the areas pack is missing)."""


def _require(store: Any, slug: str) -> Template:
    template = store.find_template(slug)
    if template is None:
        raise AreaError(f"manca il modello '{slug}': installa la Scuola «Liceo · Aree» (`zbone pack install {AREAS_PACK_NAME}`)")
    return template


def todo_list_entry(store: Any, area: str) -> Optional[Entry]:
    """The newest to-do list ("Opere e giorni") of the area, where new to-dos go."""
    found = store.list_entries(template=TODO_TEMPLATE, area=area, limit=1)
    return found[0] if found else None


def add_todo(store: Any, area: str, text: str, day: Optional[str] = None) -> Entry:
    """Add a to-do to the area's list, creating the list the first time."""
    area = parse_area(area)
    text = " ".join((text or "").split())
    if not text:
        raise AreaError("scrivi che cosa c'è da fare")
    _require(store, TODO_TEMPLATE)
    target = todo_list_entry(store, area)
    if target is None:
        return store.add_entry(TODO_TEMPLATE, {TODO_BLOCK: [{"text": text, "done": False}]}, day=day, area=area)
    items = list(target.values.get(TODO_BLOCK, [])) + [{"text": text, "done": False}]
    return store.update_entry(target.id, {TODO_BLOCK: items})


def set_todo(store: Any, todo: AreaTodo, done: bool = True) -> Entry:
    """Tick (or untick) one to-do in the entry it comes from."""
    entry = store.get_entry(todo.entry_id)
    items = [dict(item) for item in entry.values.get(todo.block, [])]
    if not 0 <= todo.index < len(items) or _todo_key(items[todo.index]["text"]) != _todo_key(todo.text):
        raise AreaError("questa voce della lista è cambiata nel frattempo: ricarica")
    items[todo.index]["done"] = bool(done)
    return store.update_entry(entry.id, {todo.block: items})


def check_in(store: Any, area: str, score: Optional[int] = None, good: str = "", better: str = "", note: str = "", day: Optional[str] = None) -> Entry:
    """A quick per-area check-in (Prosoché)."""
    area = parse_area(area)
    _require(store, CHECKIN_TEMPLATE)
    values: Dict[str, Any] = {}
    if score is not None:
        values[SCORE_BLOCK] = score
    for key, text in (("bene", good), ("meglio", better), ("nota", note)):
        if text and text.strip():
            values[key] = text
    if not values:
        raise AreaError("scrivi almeno il punteggio o una nota")
    return store.add_entry(CHECKIN_TEMPLATE, values, day=day, area=area)
