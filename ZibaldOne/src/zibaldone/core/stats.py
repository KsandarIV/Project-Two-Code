"""Theoria (le statistiche, 0.1.4): mood, scores, writing and collections over time.

Pure functions over entries and templates; `today` is always passed in.
Mood and life areas are recognised by block type and options, not by fixed
names, so they work with the built-in packs and with the user's own
templates:

- mood: every `choice` block with `values` (sera.umore, mattina.umore …),
  brought to a 1–5 scale whatever its numbers;
- areas: `scale` blocks named like the 8 areas (personale … svago), or all
  the scales of a template that has at least 4 of them;
- other scores: the remaining `scale` blocks (sera.voto, mattina.energia …).
"""

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from zibaldone.core.blocks import PROGRESS_STATUSES, BLOCK_TYPES
from zibaldone.core.brand import AREAS
from zibaldone.core.links import LinkRecord, is_person_template, plain_text
from zibaldone.core.templates import BlockSpec, Entry, Template, validate_values

MOOD_LOW, MOOD_HIGH = 1.0, 5.0
AREA_TEMPLATE_MIN_SCALES = 4
TREND_STEP = 0.25
MONTHS = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]
WEEKDAYS = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
WEEKDAYS_SHORT = ["lun", "mar", "mer", "gio", "ven", "sab", "dom"]
IN_PROGRESS = ("ongoing", "paused")
REVIEW_SLUGS = {
    "week": ("settimana", "revisione_settimanale", "week"),
    "month": ("mese", "revisione_mensile", "month"),
    "year": ("anno", "revisione_annuale", "year"),
}


# — periods —


@dataclass(frozen=True)
class Period:
    kind: str  # "day", "week" (ISO, Monday to Sunday) or "month"
    start: date
    end: date

    @property
    def key(self) -> str:
        if self.kind == "week":
            year, week, _ = self.start.isocalendar()
            return f"{year}-W{week:02d}"
        if self.kind == "month":
            return f"{self.start.year}-{self.start.month:02d}"
        return self.start.isoformat()

    @property
    def label(self) -> str:
        if self.kind == "month":
            return f"{MONTHS[self.start.month - 1]} {self.start.year}"
        if self.kind == "day":
            return f"{WEEKDAYS[self.start.weekday()]} {long_date(self.start)}"
        week = self.start.isocalendar()[1]
        return f"settimana {week} · {date_range(self.start, self.end)}"

    @property
    def noun(self) -> str:
        return {"week": "settimana", "month": "mese", "day": "giorno"}[self.kind]

    def contains(self, day: date) -> bool:
        return self.start <= day <= self.end

    def days(self) -> List[date]:
        return [self.start + timedelta(days=offset) for offset in range((self.end - self.start).days + 1)]

    def previous(self) -> "Period":
        return period_of(self.kind, self.start - timedelta(days=1))

    def next(self) -> "Period":
        return period_of(self.kind, self.end + timedelta(days=1))


def week_of(day: date) -> Period:
    start = day - timedelta(days=day.weekday())
    return Period("week", start, start + timedelta(days=6))


def month_of(day: date) -> Period:
    start = day.replace(day=1)
    following = (start + timedelta(days=32)).replace(day=1)
    return Period("month", start, following - timedelta(days=1))


def period_of(kind: str, day: date) -> Period:
    if kind == "week":
        return week_of(day)
    if kind == "month":
        return month_of(day)
    if kind == "day":
        return Period("day", day, day)
    raise ValueError(f"periodo sconosciuto: {kind} (usa giorno, settimana o mese)")


def long_date(day: date) -> str:
    return f"{day.day} {MONTHS[day.month - 1]} {day.year}"


def date_range(start: date, end: date) -> str:
    if start.year != end.year:
        return f"{long_date(start)} – {long_date(end)}"
    if start.month != end.month:
        return f"{start.day} {MONTHS[start.month - 1]} – {long_date(end)}"
    return f"{start.day}–{long_date(end)}"


def short_day(day: date) -> str:
    return f"{WEEKDAYS_SHORT[day.weekday()]} {day.day}"


def number(value: Optional[float], digits: int = 1) -> str:
    """Italian decimal comma: 3.85 -> '3,9'."""
    if value is None:
        return "—"
    text = f"{value:.{digits}f}".replace(".", ",")
    return text[:-2] if digits == 1 and text.endswith(",0") else text


def entry_date(entry: Entry) -> date:
    return date.fromisoformat(entry.day)


def updated_date(entry: Entry) -> date:
    try:
        return datetime.fromisoformat(entry.updated_at).astimezone().date()
    except (ValueError, TypeError):
        return entry_date(entry)


def in_period(entries: Iterable[Entry], period: Period) -> List[Entry]:
    return [entry for entry in entries if period.contains(entry_date(entry))]


def _average(values: Sequence[float]) -> Optional[float]:
    return sum(values) / len(values) if values else None


# — which blocks mean what —


def _plain(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower().translate(str.maketrans("àèéìòù", "aeeiou")))


def is_mood_block(spec: BlockSpec) -> bool:
    values = spec.options.get("values") if spec.type == "choice" else None
    return bool(values) and min(values) != max(values)


def mood_score(spec: BlockSpec, value: Any) -> Optional[float]:
    """The choice's number brought to 1–5 (5 the best), or None."""
    if not is_mood_block(spec) or not isinstance(value, str):
        return None
    raw = BLOCK_TYPES["choice"].score(value, spec.options)
    if raw is None:
        return None
    low, high = min(spec.options["values"]), max(spec.options["values"])
    return MOOD_LOW + (MOOD_HIGH - MOOD_LOW) * (raw - low) / (high - low)


def area_name(template: Template, spec: BlockSpec) -> Optional[str]:
    """The life area a scale block stands for, or None."""
    if spec.type != "scale":
        return None
    for candidate in (spec.key, _plain(spec.label)):
        if candidate in AREAS:
            return candidate
    scales = [block for block in template.blocks if block.type == "scale"]
    if len(scales) >= AREA_TEMPLATE_MIN_SCALES:
        return _plain(spec.label) or spec.key
    return None


def _bounds(spec: BlockSpec) -> Tuple[int, int]:
    return BLOCK_TYPES["scale"].bounds(spec.options)


# — mood —


@dataclass
class MoodPoint:
    key: str
    start: date
    end: date
    average: Optional[float]
    days: int  # days with at least one mood value


def daily_moods(entries: Iterable[Entry], templates: Dict[str, Template]) -> Dict[date, float]:
    """Average mood of each day (all mood blocks of all that day's entries)."""
    scores: Dict[date, List[float]] = {}
    for entry in entries:
        template = templates.get(entry.template)
        if template is None:
            continue
        for spec in template.blocks:
            score = mood_score(spec, entry.values.get(spec.key))
            if score is not None:
                scores.setdefault(entry_date(entry), []).append(score)
    return {day: sum(values) / len(values) for day, values in scores.items()}


def mood_series(entries: Iterable[Entry], templates: Dict[str, Template], start: date, end: date, by: str = "day") -> List[MoodPoint]:
    """Mood from `start` to `end` per day, ISO week or month (averages of the daily averages)."""
    moods = daily_moods(entries, templates)
    points: List[MoodPoint] = []
    cursor = start
    while cursor <= end:
        period = period_of(by, cursor)
        first, last = max(period.start, start), min(period.end, end)
        values = [moods[day] for day in Period("day", first, last).days() if day in moods]
        points.append(MoodPoint(period.key, first, last, _average(values), len(values)))
        cursor = last + timedelta(days=1)
    return points


@dataclass
class MoodSummary:
    average: Optional[float]
    days: int
    previous_average: Optional[float]
    best_day: Optional[date] = None
    worst_day: Optional[date] = None

    @property
    def delta(self) -> Optional[float]:
        if self.average is None or self.previous_average is None:
            return None
        return self.average - self.previous_average

    @property
    def trend(self) -> Optional[str]:
        """'up', 'down' or 'steady' compared with the previous period."""
        if self.delta is None:
            return None
        if self.delta >= TREND_STEP:
            return "up"
        if self.delta <= -TREND_STEP:
            return "down"
        return "steady"


def mood_summary(entries: Sequence[Entry], templates: Dict[str, Template], period: Period) -> MoodSummary:
    moods = daily_moods(entries, templates)
    current = {day: value for day, value in moods.items() if period.contains(day)}
    previous = period.previous()
    before = [value for day, value in moods.items() if previous.contains(day)]
    ranked = sorted(current, key=lambda day: (-current[day], day))
    return MoodSummary(
        average=_average(list(current.values())),
        days=len(current),
        previous_average=_average(before),
        best_day=ranked[0] if ranked else None,
        worst_day=ranked[-1] if len(ranked) > 1 else None,
    )


# — scores (scale blocks) —


@dataclass
class ScaleStat:
    key: str  # area name, or "template.block"
    label: str
    template_name: str
    average: float
    count: int
    low: int
    high: int
    area: bool

    @property
    def normalized(self) -> float:
        return (self.average - self.low) / (self.high - self.low) if self.high > self.low else 0.0


def scale_averages(entries: Iterable[Entry], templates: Dict[str, Template], period: Optional[Period] = None) -> List[ScaleStat]:
    """Average of every scale block in the period: areas merged by name, the others by template and block."""
    collected: Dict[str, Dict[str, Any]] = {}
    for entry in entries:
        if period and not period.contains(entry_date(entry)):
            continue
        template = templates.get(entry.template)
        if template is None:
            continue
        for spec in template.blocks:
            value = entry.values.get(spec.key)
            if spec.type != "scale" or value is None:
                continue
            area = area_name(template, spec)
            key = area or f"{template.slug}.{spec.key}"
            low, high = _bounds(spec)
            slot = collected.setdefault(key, {"label": spec.label, "template": "" if area else template.name, "values": [], "area": bool(area), "low": low, "high": high})
            if (slot["low"], slot["high"]) != (low, high):
                value = slot["low"] + (slot["high"] - slot["low"]) * (value - low) / (high - low)
            slot["values"].append(value)
    stats = [
        ScaleStat(key, slot["label"], slot["template"], sum(slot["values"]) / len(slot["values"]), len(slot["values"]), slot["low"], slot["high"], slot["area"])
        for key, slot in collected.items()
    ]
    order = {name: index for index, name in enumerate(AREAS)}
    return sorted(stats, key=lambda stat: (not stat.area, order.get(stat.key, len(order)), stat.template_name, stat.label))


def best_and_worst_area(stats: Sequence[ScaleStat]) -> Tuple[Optional[ScaleStat], Optional[ScaleStat]]:
    """The highest and the lowest area; no lowest when there is only one, or when all are level."""
    areas = sorted((stat for stat in stats if stat.area), key=lambda stat: (-stat.normalized, stat.label))
    if len(areas) < 2 or areas[0].normalized <= areas[-1].normalized:
        return (areas[0] if areas else None), None
    return areas[0], areas[-1]


# — writing activity —


@dataclass
class Activity:
    total: int
    active_days: int
    days: int
    per_day: Dict[date, int]
    per_template: List[Tuple[str, str, int]]  # (slug, name, count), most used first
    current_streak: int
    longest_streak: int


def streaks(days: Set[date], today: date) -> Tuple[int, int]:
    """(current, longest) runs of consecutive days with entries. Today still counts as open."""
    current = 0
    cursor = today if today in days else today - timedelta(days=1)
    while cursor in days:
        current += 1
        cursor -= timedelta(days=1)
    longest = run = 0
    previous: Optional[date] = None
    for day in sorted(day for day in days if day <= today):
        run = run + 1 if previous is not None and (day - previous).days == 1 else 1
        longest = max(longest, run)
        previous = day
    return current, longest


def writing_activity(entries: Sequence[Entry], templates: Dict[str, Template], period: Period, today: date) -> Activity:
    inside = in_period(entries, period)
    per_day = {day: 0 for day in period.days()}
    counts: Dict[str, int] = {}
    for entry in inside:
        per_day[entry_date(entry)] += 1
        counts[entry.template] = counts.get(entry.template, 0) + 1
    names = {slug: templates[slug].name if slug in templates else slug for slug in counts}
    current, longest = streaks({entry_date(entry) for entry in entries}, today)
    return Activity(
        total=len(inside),
        active_days=sum(1 for count in per_day.values() if count),
        days=len(per_day),
        per_day=per_day,
        per_template=sorted(((slug, names[slug], count) for slug, count in counts.items()), key=lambda item: (-item[2], item[1])),
        current_streak=current,
        longest_streak=longest,
    )


# — collections (progress blocks) —


@dataclass
class ProgressItem:
    entry_id: str
    title: str
    template: str
    template_name: str
    status: str
    current: Optional[float]
    total: Optional[float]
    unit: str
    bookmark: str
    updated: date

    @property
    def status_label(self) -> str:
        return PROGRESS_STATUSES.get(self.status, self.status)

    @property
    def percent(self) -> Optional[int]:
        if self.current is None or not self.total:
            return 100 if self.status == "completed" else None
        return max(0, min(100, round(100 * self.current / self.total)))


def progress_items(entries: Iterable[Entry], templates: Dict[str, Template]) -> List[ProgressItem]:
    items = []
    for entry in entries:
        template = templates.get(entry.template)
        if template is None:
            continue
        bookmark = next((str(entry.values[spec.key]) for spec in template.blocks if spec.type == "bookmark" and spec.key in entry.values), "")
        for spec in template.blocks:
            value = entry.values.get(spec.key)
            if spec.type != "progress" or not isinstance(value, dict):
                continue
            items.append(ProgressItem(
                entry.id, entry.title(template), template.slug, template.name, value.get("status", "not_started"),
                value.get("current"), value.get("total"), spec.options.get("unit", ""), bookmark, updated_date(entry),
            ))
            break
    return items


@dataclass
class Collections:
    in_progress: List[ProgressItem]
    completed: List[ProgressItem]


def collections(entries: Iterable[Entry], templates: Dict[str, Template], today: date, recent_days: int = 30, period: Optional[Period] = None) -> Collections:
    """What is in progress (ongoing or paused, most recently touched first) and what was completed lately.

    "Completed lately" means updated as completed in `period`, or in the last `recent_days` days.
    """
    items = progress_items(entries, templates)
    window = period or Period("day", today - timedelta(days=recent_days - 1), today)
    ongoing = sorted((item for item in items if item.status in IN_PROGRESS), key=lambda item: (item.status != "ongoing", -item.updated.toordinal(), item.title))
    done = sorted((item for item in items if item.status == "completed" and window.contains(item.updated)), key=lambda item: (-item.updated.toordinal(), item.title))
    return Collections(ongoing, done)


# — open checklist items and people —


@dataclass
class OpenItem:
    text: str
    day: date
    entry_id: str
    template_name: str
    block_label: str


def open_items(entries: Sequence[Entry], templates: Dict[str, Template], period: Period, exclude: Sequence[str] = ()) -> List[OpenItem]:
    """Unticked checklist items of the period; an item ticked later (same text) is not open any more."""
    state: Dict[str, Tuple[bool, OpenItem]] = {}
    for entry in sorted(in_period(entries, period), key=lambda entry: (entry.day, entry.created_at)):
        template = templates.get(entry.template)
        if template is None or template.slug in exclude:
            continue
        for spec in template.blocks:
            if spec.type != "checklist":
                continue
            for item in entry.values.get(spec.key, []):
                key = " ".join(item["text"].lower().split())
                state[key] = (item["done"], OpenItem(item["text"], entry_date(entry), entry.id, template.name, spec.label))
    return [item for done, item in state.values() if not done]


@dataclass
class PersonCount:
    entry_id: str
    title: str
    count: int


def most_linked_people(entries: Sequence[Entry], templates: Dict[str, Template], links: Iterable[LinkRecord], period: Optional[Period] = None, limit: int = 5) -> List[PersonCount]:
    """People most often linked (link blocks or [[Nome]]) from entries of the period."""
    by_id = {entry.id: entry for entry in entries}
    sources = {entry.id for entry in entries if period is None or period.contains(entry_date(entry))}
    linked: Dict[str, Set[str]] = {}
    for link in links:
        target = by_id.get(link.target or "")
        if link.source not in sources or target is None or link.source == target.id:
            continue
        template = templates.get(target.template)
        if template is not None and is_person_template(template):
            linked.setdefault(target.id, set()).add(link.source)
    counts = [PersonCount(entry_id, by_id[entry_id].title(templates[by_id[entry_id].template]), len(found)) for entry_id, found in linked.items()]
    return sorted(counts, key=lambda item: (-item.count, item.title))[:limit]


# — reviews (Hypomnemata for the week, Lettera a Lucilio for the month) —


@dataclass
class Moment:
    day: date
    text: str


@dataclass
class Review:
    period: Period
    previous: Period
    activity: Activity
    previous_entries: int
    mood: MoodSummary
    mood_points: List[MoodPoint]
    scales: List[ScaleStat]
    best_area: Optional[ScaleStat]
    worst_area: Optional[ScaleStat]
    completed: List[ProgressItem]
    in_progress: List[ProgressItem]
    open_items: List[OpenItem]
    people: List[PersonCount]
    moments: List[Moment] = field(default_factory=list)
    learned: List[Moment] = field(default_factory=list)

    @property
    def entries(self) -> int:
        return self.activity.total


def _first_sentence(text: str, limit: int = 140) -> str:
    text = " ".join(plain_text(text).split())
    match = re.match(r"(.+?[.!?])(\s|$)", text)
    sentence = match.group(1) if match else text
    return sentence if len(sentence) <= limit else sentence[: limit - 1].rstrip() + "…"


def _matches(spec: BlockSpec, *needles: str) -> bool:
    haystack = f"{spec.key} {spec.label}".lower()
    return any(needle in haystack for needle in needles)


def _moments(inside: Sequence[Entry], templates: Dict[str, Template], moods: Dict[date, float], completed: Sequence[ProgressItem], limit: int = 6) -> List[Moment]:
    """Something from the best days: titles of titled entries, else the first sentence written that day."""
    by_day: Dict[date, List[str]] = {}
    for entry in sorted(inside, key=lambda entry: (entry.day, entry.created_at)):
        template = templates.get(entry.template)
        if template is None:
            continue
        if is_person_template(template):
            continue
        if template.title_key and entry.values.get(template.title_key) and not any(spec.type == "progress" for spec in template.blocks):
            by_day.setdefault(entry_date(entry), []).append(str(entry.values[template.title_key]))
            continue
        for spec in template.blocks:
            if spec.type == "longtext" and entry.values.get(spec.key) and not _matches(spec, "impar", "domani", "difficol"):
                by_day.setdefault(entry_date(entry), []).append(_first_sentence(entry.values[spec.key]))
                break
    # Days without a mood count as fairly good: an encounter on such a day is still a moment.
    good_days = sorted((day for day in by_day if moods.get(day, 3.5) >= 3.5), key=lambda day: (-moods.get(day, 3.5), day))
    moments = [Moment(day, "; ".join(dict.fromkeys(by_day[day]))) for day in sorted(good_days[:limit])]
    moments += [Moment(item.updated, f"Completato: {item.title}") for item in completed[: max(0, limit - len(moments))]]
    return moments


def _learned(inside: Sequence[Entry], templates: Dict[str, Template], limit: int = 7) -> List[Moment]:
    found = []
    for entry in sorted(inside, key=lambda entry: (entry.day, entry.created_at)):
        template = templates.get(entry.template)
        for spec in template.blocks if template else []:
            if spec.type == "longtext" and entry.values.get(spec.key) and _matches(spec, "impar", "lezion"):
                found.append(Moment(entry_date(entry), _first_sentence(entry.values[spec.key], 200)))
    return found[:limit]


def review(
    entries: Sequence[Entry], templates: Dict[str, Template], links: Iterable[LinkRecord], kind: str, day: date, today: date,
    exclude_templates: Sequence[str] = (),
) -> Review:
    """Everything a weekly or monthly review needs. `day` picks the period, `today` drives the streaks."""
    period = period_of(kind, day)
    previous = period.previous()
    entries = [entry for entry in entries if entry.template not in exclude_templates]
    inside = in_period(entries, period)
    scales = scale_averages(entries, templates, period)
    best, worst = best_and_worst_area(scales)
    found = collections(entries, templates, today, period=period)
    moods = daily_moods(inside, templates)
    return Review(
        period=period,
        previous=previous,
        activity=writing_activity(entries, templates, period, today),
        previous_entries=len(in_period(entries, previous)),
        mood=mood_summary(entries, templates, period),
        mood_points=mood_series(entries, templates, period.start, period.end, "day" if kind == "week" else "week"),
        scales=scales,
        best_area=best,
        worst_area=worst,
        completed=found.completed,
        in_progress=found.in_progress,
        open_items=open_items(entries, templates, period),
        people=most_linked_people(entries, templates, list(links), period),
        moments=_moments(inside, templates, moods, found.completed),
        learned=_learned(inside, templates),
    )


def weekly_review(entries: Sequence[Entry], templates: Dict[str, Template], links: Iterable[LinkRecord], day: date, today: date) -> Review:
    return review(entries, templates, links, "week", day, today, exclude_templates=review_slugs(templates))


def monthly_review(entries: Sequence[Entry], templates: Dict[str, Template], links: Iterable[LinkRecord], day: date, today: date) -> Review:
    return review(entries, templates, links, "month", day, today, exclude_templates=review_slugs(templates))


def review_slugs(templates: Dict[str, Template]) -> List[str]:
    """Templates holding reviews (settimana, mese, anno and their copies): left out of the reviews' numbers."""
    wanted = [name for names in REVIEW_SLUGS.values() for name in names]
    return sorted(slug for slug in templates if any(slug == name or slug.startswith(name + "_") for name in wanted))


def review_template(templates: Dict[str, Template], kind: str) -> Optional[Template]:
    """The template that holds this kind of review: 'settimana' or 'mese' (also a copy like 'settimana_2')."""
    for wanted in REVIEW_SLUGS[kind]:
        for slug in sorted(templates):
            if slug == wanted or slug.startswith(wanted + "_"):
                return templates[slug]
    return None


def _lines(moments: Sequence[Moment]) -> str:
    return "\n".join(f"- {short_day(moment.day)}: {moment.text}" for moment in moments)


def propose_review_values(result: Review, template: Template) -> Dict[str, Any]:
    """Pre-filled values for a review template (settimana, mese or one of the user's).

    A draft to edit, never a judgement: difficult moments are left to the user.
    Blocks are matched by type and name: the first scale is the vote, a choice
    listing the areas gets the area that needs most care, a checklist gets
    the items still open, long texts get the good moments and what was learned.
    """
    values: Dict[str, Any] = {}
    vote_done = False
    for spec in template.blocks:
        if spec.type == "scale" and not vote_done:
            vote = _proposed_vote(result, spec)
            if vote is not None:
                values[spec.key] = vote
            vote_done = True
        elif spec.type == "choice" and result.worst_area is not None:
            for choice in spec.options.get("choices", []):
                if _plain(choice) == _plain(result.worst_area.label) or _plain(choice) == result.worst_area.key:
                    values[spec.key] = choice
                    break
        elif spec.type == "checklist" and result.open_items:
            limit = spec.options.get("max_items", 100)
            values[spec.key] = [{"text": item.text, "done": False} for item in result.open_items[: min(limit, 10)]]
        elif spec.type == "longtext":
            if _matches(spec, "bell", "moment", "positiv", "gratit") and result.moments:
                values[spec.key] = _lines(result.moments)
            elif _matches(spec, "impar", "lezion") and result.learned:
                values[spec.key] = _lines(result.learned)
    return validate_values(template, values, partial=True)


def _proposed_vote(result: Review, spec: BlockSpec) -> Optional[int]:
    low, high = _bounds(spec)
    votes = [stat for stat in result.scales if not stat.area and stat.key.endswith(".voto")]
    if votes:
        normalized = sum(stat.normalized * stat.count for stat in votes) / sum(stat.count for stat in votes)
    elif result.mood.average is not None:
        normalized = (result.mood.average - MOOD_LOW) / (MOOD_HIGH - MOOD_LOW)
    else:
        return None
    return int(round(low + normalized * (high - low)))


# — words for the summaries (never a reproach) —


def trend_words(summary: MoodSummary, noun: str) -> str:
    previous = f"{'della' if noun in ('settimana',) else 'del'} {noun} prima"
    if summary.trend == "up":
        return f"più su {previous} ({number(summary.previous_average)})"
    if summary.trend == "down":
        return f"un po' più giù {previous} ({number(summary.previous_average)})"
    if summary.trend == "steady":
        return f"simile {'alla' if noun == 'settimana' else 'al'} {noun} prima ({number(summary.previous_average)})"
    return ""


def bar(fraction: Optional[float], width: int = 10) -> str:
    if fraction is None:
        return "·" * width
    filled = max(0, min(width, round(fraction * width)))
    return "█" * filled + "░" * (width - filled)


# — HTML export: small inline SVG charts in the app theme —

STATS_CSS = """
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:16px}
.tile .value{font-size:28px;font-weight:600;color:%(text)s}
.tile .label{color:%(muted)s;font-size:13px}
.charts{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px}
svg.chart{display:block;width:100%%;height:auto}
.grid-line{stroke:%(line)s;stroke-width:1}
.axis{fill:%(muted)s;font-size:11px;font-variant-numeric:tabular-nums}
.value-label{fill:%(text)s;font-size:11px;font-variant-numeric:tabular-nums}
.hit{fill:transparent;cursor:default}
.hit:focus{outline:none;stroke:%(text)s;stroke-width:1}
table{border-collapse:collapse;width:100%%;font-size:13px;font-variant-numeric:tabular-nums}
td,th{text-align:left;padding:3px 6px;border-bottom:1px solid %(line)s}
details{margin-top:8px}
summary{cursor:pointer;color:%(muted)s}
#tip{position:fixed;pointer-events:none;font-size:13px}
section.panel{margin-bottom:16px}
"""

STATS_SCRIPT = r"""
(function () {
  var tip = document.getElementById('tip');
  function show(target, x, y) { tip.textContent = target.getAttribute('data-tip'); tip.style.left = (x + 12) + 'px'; tip.style.top = (y + 12) + 'px'; tip.hidden = false; }
  Array.prototype.forEach.call(document.querySelectorAll('[data-tip]'), function (target) {
    target.addEventListener('pointermove', function (event) { show(target, event.clientX, event.clientY); });
    target.addEventListener('pointerleave', function () { tip.hidden = true; });
    target.addEventListener('focus', function () { var box = target.getBoundingClientRect(); show(target, box.right, box.top); });
    target.addEventListener('blur', function () { tip.hidden = true; });
  });
})();
"""


def _mood_chart(points: Sequence[MoodPoint], esc: Any, accent: str, surface: str) -> str:
    width, height, left, right, top, bottom = 520, 200, 34, 12, 14, 30
    plot_w, plot_h = width - left - right, height - top - bottom
    count = max(len(points), 1)
    step = plot_w / max(count - 1, 1)

    def x_of(index: int) -> float:
        return left + (index * step if count > 1 else plot_w / 2)

    def y_of(value: float) -> float:
        return top + plot_h * (MOOD_HIGH - value) / (MOOD_HIGH - MOOD_LOW)

    parts = []
    for level in range(1, 6):
        y = y_of(level)
        parts.append(f'<line class="grid-line" x1="{left}" x2="{width - right}" y1="{y:.1f}" y2="{y:.1f}"/>')
        parts.append(f'<text class="axis" x="{left - 8}" y="{y + 4:.1f}" text-anchor="end">{level}</text>')
    runs: List[List[str]] = [[]]
    for index, point in enumerate(points):
        if point.average is None:
            runs.append([])
            continue
        runs[-1].append(f"{x_of(index):.1f},{y_of(point.average):.1f}")
    for run in runs:
        if len(run) > 1:
            parts.append(f'<polyline points="{" ".join(run)}" fill="none" stroke="{accent}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>')
    labelled = max(1, count // 8)
    for index, point in enumerate(points):
        x = x_of(index)
        name = short_day(point.start) if point.start == point.end else f"{point.start.day}/{point.start.month}"
        if index % labelled == 0:
            parts.append(f'<text class="axis" x="{x:.1f}" y="{height - 10}" text-anchor="middle">{esc(name)}</text>')
        if point.average is None:
            continue
        y = y_of(point.average)
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{accent}" stroke="{surface}" stroke-width="2"/>')
        tip = f"{name}: umore {number(point.average)} su 5"
        parts.append(f'<circle class="hit" tabindex="0" data-tip="{esc(tip)}" cx="{x:.1f}" cy="{y:.1f}" r="12"><title>{esc(tip)}</title></circle>')
    last = next((index for index in range(len(points) - 1, -1, -1) if points[index].average is not None), None)
    if last is not None:
        parts.append(f'<text class="value-label" x="{x_of(last):.1f}" y="{y_of(points[last].average) - 10:.1f}" text-anchor="middle">{number(points[last].average)}</text>')
    return f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-label="Andamento dell\'umore">{"".join(parts)}</svg>'


def _bars(rows: Sequence[Tuple[str, float, float, str]], esc: Any, accent: str, label: str) -> str:
    """Horizontal bars: (name, fraction 0..1, value, value text)."""
    bar_h, gap, left, right = 14, 12, 110, 48
    width = 520
    height = len(rows) * (bar_h + gap) + gap
    plot_w = width - left - right
    parts = [f'<line class="grid-line" x1="{left}" x2="{left}" y1="0" y2="{height}"/>']
    for index, (name, fraction, _, text) in enumerate(rows):
        y = gap + index * (bar_h + gap)
        length = max(0.0, min(1.0, fraction)) * plot_w
        radius = min(4.0, length / 2, bar_h / 2)
        if length > 0:
            parts.append(
                f'<path d="M{left},{y} h{length - radius:.1f} a{radius:.1f},{radius:.1f} 0 0 1 {radius:.1f},{radius:.1f} '
                f'v{bar_h - 2 * radius:.1f} a{radius:.1f},{radius:.1f} 0 0 1 {-radius:.1f},{radius:.1f} h{-(length - radius):.1f} z" fill="{accent}"/>'
            )
        parts.append(f'<text class="axis" x="{left - 8}" y="{y + bar_h - 3}" text-anchor="end">{esc(name[:16])}</text>')
        parts.append(f'<text class="value-label" x="{left + length + 6:.1f}" y="{y + bar_h - 3}">{esc(text)}</text>')
        parts.append(f'<rect class="hit" tabindex="0" data-tip="{esc(name + ": " + text)}" x="0" y="{y - gap / 2}" width="{width}" height="{bar_h + gap}"><title>{esc(name + ": " + text)}</title></rect>')
    return f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-label="{esc(label)}">{"".join(parts)}</svg>'


def _columns(rows: Sequence[Tuple[str, int]], esc: Any, accent: str) -> str:
    width, height, top, bottom, left = 520, 150, 16, 26, 8
    plot_h = height - top - bottom
    slot = (width - 2 * left) / max(len(rows), 1)
    thick = min(24.0, slot * 0.6)
    top_value = max([count for _, count in rows] + [1])
    labelled = max(1, len(rows) // 10)
    parts = [f'<line class="grid-line" x1="{left}" x2="{width - left}" y1="{top + plot_h}" y2="{top + plot_h}"/>']
    for index, (name, count) in enumerate(rows):
        x = left + index * slot + (slot - thick) / 2
        length = plot_h * count / top_value
        radius = min(4.0, thick / 2, length)
        base = top + plot_h
        if count:
            parts.append(
                f'<path d="M{x:.1f},{base} v{-(length - radius):.1f} a{radius:.1f},{radius:.1f} 0 0 1 {radius:.1f},{-radius:.1f} '
                f'h{thick - 2 * radius:.1f} a{radius:.1f},{radius:.1f} 0 0 1 {radius:.1f},{radius:.1f} v{length - radius:.1f} z" fill="{accent}"/>'
            )
            if len(rows) <= 14:
                parts.append(f'<text class="value-label" x="{x + thick / 2:.1f}" y="{base - length - 4:.1f}" text-anchor="middle">{count}</text>')
        if index % labelled == 0:
            parts.append(f'<text class="axis" x="{x + thick / 2:.1f}" y="{height - 8}" text-anchor="middle">{esc(name)}</text>')
        tip = f"{name}: {count} voc{'e' if count == 1 else 'i'}"
        parts.append(f'<rect class="hit" tabindex="0" data-tip="{esc(tip)}" x="{left + index * slot:.1f}" y="{top}" width="{slot:.1f}" height="{plot_h}"><title>{esc(tip)}</title></rect>')
    return f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-label="Voci per giorno">{"".join(parts)}</svg>'


def _table(headers: Sequence[str], rows: Sequence[Sequence[str]], esc: Any) -> str:
    head = "".join(f"<th>{esc(item)}</th>" for item in headers)
    body = "".join("<tr>" + "".join(f"<td>{esc(cell)}</td>" for cell in row) + "</tr>" for row in rows)
    return f"<details><summary>Vedi i numeri</summary><table><tr>{head}</tr>{body}</table></details>"


def render_html(result: Review, title: str = "Theoria", proposal: Optional[Sequence[Tuple[str, str]]] = None) -> str:
    """The period's numbers as one self-contained page (inline SVG, no external files)."""
    from zibaldone.core.graph import THEME, esc, html_page

    accent, surface = THEME["accent"], THEME["panel"]
    mood = result.mood
    tiles = [
        ("voci", str(result.entries), f"la {result.period.noun} prima: {result.previous_entries}" if result.period.kind == "week" else f"il mese prima: {result.previous_entries}"),
        ("giorni con almeno una voce", f"{result.activity.active_days} su {result.activity.days}", ""),
        ("umore medio (1–5)", number(mood.average), trend_words(mood, result.period.noun)),
        ("giorni di fila", str(result.activity.current_streak), f"la serie più lunga: {result.activity.longest_streak}"),
    ]
    tile_html = "".join(
        f'<div class="tile panel"><div class="value">{esc(value)}</div><div class="label">{esc(label)}</div>'
        + (f'<div class="muted">{esc(note)}</div>' if note else "") + "</div>"
        for label, value, note in tiles
    )
    sections = []
    if any(point.average is not None for point in result.mood_points):
        rows = [(point.key, number(point.average), str(point.days)) for point in result.mood_points]
        sections.append(
            '<section class="panel"><h2>Umore</h2>' + _mood_chart(result.mood_points, esc, accent, surface)
            + _table(["periodo", "umore medio", "giorni"], rows, esc) + "</section>"
        )
    days = sorted(result.activity.per_day)
    if days:
        columns = [(short_day(day) if len(days) <= 14 else str(day.day), result.activity.per_day[day]) for day in days]
        sections.append(
            '<section class="panel"><h2>Scrittura</h2>' + _columns(columns, esc, accent)
            + _table(["giorno", "voci"], [(day.isoformat(), str(result.activity.per_day[day])) for day in days], esc) + "</section>"
        )
    areas = [stat for stat in result.scales if stat.area]
    if areas:
        rows = [(stat.label, stat.normalized, stat.average, f"{number(stat.average)}/{stat.high}") for stat in areas]
        sections.append(
            '<section class="panel"><h2>Aree della vita</h2>' + _bars(rows, esc, accent, "Media delle aree")
            + _table(["area", "media", "valori"], [(stat.label, number(stat.average), str(stat.count)) for stat in areas], esc) + "</section>"
        )
    others = [stat for stat in result.scales if not stat.area]
    if others:
        rows = [(f"{stat.label}", stat.normalized, stat.average, f"{number(stat.average)}/{stat.high}") for stat in others]
        sections.append('<section class="panel"><h2>Altri punteggi</h2>' + _bars(rows, esc, accent, "Altri punteggi") + "</section>")
    lists = []
    if result.in_progress:
        lists.append("<h2>In corso</h2><ul>" + "".join(
            f"<li>{esc(item.title)} <span class=\"muted\">({esc(item.template_name)}{', ' + str(item.percent) + '%' if item.percent is not None else ''})</span></li>"
            for item in result.in_progress[:10]) + "</ul>")
    if result.completed:
        lists.append("<h2>Completati</h2><ul>" + "".join(f"<li>{esc(item.title)} <span class=\"muted\">({esc(item.template_name)})</span></li>" for item in result.completed) + "</ul>")
    if result.people:
        lists.append("<h2>Persone più presenti</h2><ul>" + "".join(f"<li>{esc(person.title)} <span class=\"muted\">({person.count})</span></li>" for person in result.people) + "</ul>")
    if result.open_items:
        lists.append("<h2>Ancora aperti</h2><ul>" + "".join(f"<li>{esc(item.text)}</li>" for item in result.open_items[:15]) + "</ul>")
    if proposal:
        lists.append("<h2>Proposta per la revisione</h2><ul>" + "".join(f"<li><strong>{esc(label)}</strong>: {esc(text)}</li>" for label, text in proposal) + "</ul>")
    if lists:
        sections.append('<section class="panel">' + "".join(lists) + "</section>")
    if not sections:
        sections.append('<section class="panel"><p>Ancora niente da mostrare per questo periodo.</p></section>')
    body = f'<div class="tiles">{tile_html}</div><div class="charts">{"".join(sections)}</div><div id="tip" class="panel" hidden></div>'
    return html_page(title, result.period.label, body, STATS_SCRIPT, STATS_CSS % THEME)
