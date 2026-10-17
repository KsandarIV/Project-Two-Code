"""What each screen shows, computed without Flet.

Functions here read a `Store` (or plain data) and return small dataclasses
the views turn into controls. Dates are Italian; `now`/`today` are always
passed in, so tests choose the clock.
"""

import math
import unicodedata
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from zibaldone.core.blocks import BLOCK_TYPES, PROGRESS_STATUSES, is_number
from zibaldone.core.brand import AREAS, MASCOTS, Mascot, Quote, mascot_for, quote_of_the_day
from zibaldone.core.packs import InstallPlan, Pack, build_pack, write_pack_file
from zibaldone.core.reminders import MOMENT_LABELS, MOMENTS, WEEKDAY_NAMES, MomentConfig, QuietHours, ReminderConfig
from zibaldone.core.templates import SLUG, BlockSpec, Entry, Template, slugify, validate_values
from zibaldone.ui import forms
from zibaldone.ui.theme import ACCENT, CATEGORICAL, TEXT_DIM, color_or

# * — Italian dates —

MONTHS = ("gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre")
MONTHS_SHORT = ("gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic")
WEEKDAYS = ("lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica")


def italian_date(day: date, weekday: bool = True) -> str:
    """'sabato 17 ottobre 2026' (or '17 ottobre 2026')."""
    text = f"{day.day} {MONTHS[day.month - 1]} {day.year}"
    return f"{WEEKDAYS[day.weekday()]} {text}" if weekday else text


def _as_date(value: Any) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def short_date(value: Any, today: date) -> str:
    """'oggi', 'ieri', '17 ott' (this year) or '17 ott 2025'."""
    day = _as_date(value)
    if day is None:
        return str(value)
    delta = (today - day).days
    if delta == 0:
        return "oggi"
    if delta == 1:
        return "ieri"
    if delta == -1:
        return "domani"
    text = f"{day.day} {MONTHS_SHORT[day.month - 1]}"
    return text if day.year == today.year else f"{text} {day.year}"


def picked_date(value: Any) -> Optional[date]:
    """The day chosen in a date picker. Flet sends datetimes in UTC: read them in local time."""
    if isinstance(value, datetime):
        return (value.astimezone() if value.tzinfo else value).date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        return picked_date(datetime.fromisoformat(value))
    return None


def greeting(now: datetime) -> str:
    hour = now.hour
    if 5 <= hour < 13:
        return "Buongiorno"
    if 13 <= hour < 18:
        return "Buon pomeriggio"
    return "Buonasera"


def local_timestamp(text: str) -> str:
    """An ISO UTC timestamp as local '17 ott 2026, 21:30'."""
    try:
        moment = datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return str(text or "")
    if moment.tzinfo is not None:
        moment = moment.astimezone()
    return f"{moment.day} {MONTHS_SHORT[moment.month - 1]} {moment.year}, {moment:%H:%M}"


def _plain(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", (text or "").lower())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


# * — entries as rows —


@dataclass(frozen=True)
class EntryRow:
    id: str
    title: str
    template_slug: str
    template_name: str
    icon: str
    color: str
    day: str
    day_label: str
    summary: str


def entry_summary(entry: Entry, template: Template, limit: int = 90) -> str:
    """A one-line taste of the entry: the first filled blocks after the title."""
    parts: List[str] = []
    for spec in template.blocks:
        if spec.key == template.title_key or spec.key not in entry.values:
            continue
        if spec.type == "link":
            continue
        text = " ".join(spec.block_type.to_text(entry.values[spec.key], spec.options).split())
        if text:
            parts.append(text)
        if sum(len(part) for part in parts) > limit:
            break
    summary = " · ".join(parts)
    return summary if len(summary) <= limit else summary[: limit - 1].rstrip() + "…"


def entry_row(entry: Entry, template: Template, today: date) -> EntryRow:
    return EntryRow(
        id=entry.id,
        title=forms.entry_title(entry, template),
        template_slug=template.slug,
        template_name=template.name,
        icon=template.icon,
        color=color_or(template.color),
        day=entry.day,
        day_label=short_date(entry.day, today),
        summary=entry_summary(entry, template),
    )


@dataclass
class EntryQuery:
    """Filters of the Voci screen. Text goes to the full-text search (Zetesis, 0.1.2)."""

    template: str = ""
    day_from: str = ""
    day_to: str = ""
    text: str = ""


def list_entry_rows(store: Any, query: EntryQuery, today: date, limit: int = 300) -> List[EntryRow]:
    templates = {template.slug: template for template in store.list_templates()}
    day_from, day_to = query.day_from or None, query.day_to or None
    if day_from and day_to and day_from > day_to:
        day_from, day_to = day_to, day_from
    text = query.text.strip()
    rows: List[EntryRow] = []
    if text:
        # every block, best match first; the summary becomes the piece of text that matched
        found = store.search(text, template=query.template or None, since=day_from, until=day_to, limit=limit)
        for hit in found.hits:
            template = templates.get(hit.entry.template)
            if template is None:
                continue
            row = entry_row(hit.entry, template, today)
            rows.append(replace(row, summary=hit.snippet.text) if hit.snippet else row)
        return rows
    for entry in store.list_entries(template=query.template or None, day_from=day_from, day_to=day_to):
        template = templates.get(entry.template)
        if template is None:
            continue
        rows.append(entry_row(entry, template, today))
        if len(rows) >= limit:
            break
    return rows


# * — Oggi · Hic et nunc —


@dataclass(frozen=True)
class MomentCard:
    key: str
    label: str
    template_name: str
    icon: str
    color: str
    installed: bool
    entry_id: str = ""
    time: str = ""

    @property
    def written(self) -> bool:
        return bool(self.entry_id)


@dataclass(frozen=True)
class AreaScore:
    area: str
    label: str
    value: Optional[int]
    maximum: int
    mascot: Optional[Mascot]

    @property
    def color(self) -> str:
        return self.mascot.color if self.mascot else ACCENT

    @property
    def fraction(self) -> float:
        return 0.0 if self.value is None or not self.maximum else self.value / self.maximum


@dataclass(frozen=True)
class AreaCheckin:
    installed: bool
    entry_id: str = ""
    scores: Tuple[AreaScore, ...] = ()

    @property
    def done(self) -> bool:
        return bool(self.entry_id)


@dataclass(frozen=True)
class ReminderBanner:
    moment: str
    title: str
    body: str


@dataclass(frozen=True)
class TodayModel:
    today: date
    date_label: str
    greeting: str
    quote: Quote
    reminder: Optional[ReminderBanner]
    moments: Tuple[MomentCard, ...]
    areas: AreaCheckin
    entries: Tuple[EntryRow, ...]
    streak: int
    diario_installed: bool

    @property
    def streak_label(self) -> str:
        if self.streak <= 0:
            return ""
        return "1 giorno" if self.streak == 1 else f"{self.streak} giorni di fila"


def area_scores(template: Optional[Template], values: Mapping[str, Any]) -> Tuple[AreaScore, ...]:
    scores = []
    for area in AREAS:
        spec = None
        if template is not None:
            spec = next((block for block in template.blocks if block.key == area), None)
        maximum = int(spec.options.get("max", 10)) if spec else 10
        label = spec.label if spec else area.capitalize()
        value = values.get(area)
        scores.append(AreaScore(area, label, value if is_number(value) else None, maximum, mascot_for(area)))
    return tuple(scores)


def build_today(
    store: Any,
    now: datetime,
    reminder: Any = None,
    streak_days: int = 0,
    reminder_config: Optional[ReminderConfig] = None,
) -> TodayModel:
    """Everything the Oggi screen shows. `reminder` is a core Reminder (or None)."""
    today = now.date()
    templates = {template.slug: template for template in store.list_templates()}
    todays = store.list_entries(day_from=today.isoformat(), day_to=today.isoformat())
    by_template: Dict[str, Entry] = {}
    for entry in reversed(todays):  # newest wins
        by_template[entry.template] = entry
    times = {moment.key: moment.time for moment in (reminder_config.moments if reminder_config else ())}
    moments = []
    for key in MOMENTS:
        template = templates.get(key)
        entry = by_template.get(key)
        moments.append(
            MomentCard(
                key=key,
                label=MOMENT_LABELS[key],
                template_name=template.name if template else "",
                icon=template.icon if template else "",
                color=color_or(template.color if template else ""),
                installed=template is not None,
                entry_id=entry.id if entry else "",
                time=times.get(key, ""),
            )
        )
    areas_template = templates.get("aree")
    areas_entry = by_template.get("aree")
    areas = AreaCheckin(
        installed=areas_template is not None,
        entry_id=areas_entry.id if areas_entry else "",
        scores=area_scores(areas_template, areas_entry.values if areas_entry else {}),
    )
    rows = tuple(entry_row(entry, templates[entry.template], today) for entry in todays if entry.template in templates)
    banner = ReminderBanner(reminder.moment, reminder.title, reminder.body) if reminder is not None else None
    return TodayModel(
        today=today,
        date_label=italian_date(today),
        greeting=greeting(now),
        quote=quote_of_the_day(today),
        reminder=banner,
        moments=tuple(moments),
        areas=areas,
        entries=rows,
        streak=streak_days,
        diario_installed=all(key in templates for key in MOMENTS),
    )


# * — one entry in detail —


@dataclass(frozen=True)
class DetailBlock:
    key: str
    label: str
    type: str
    text: str
    value: Any
    options: Mapping[str, Any]
    links: Tuple[Tuple[str, str], ...] = ()  # (id, title) for link blocks


@dataclass(frozen=True)
class EntryDetail:
    entry: Entry
    template: Template
    title: str
    day_label: str
    created_label: str
    updated_label: str
    blocks: Tuple[DetailBlock, ...]
    # 0.1.2: who links here and who names it without a link ("tutto su Marco")
    backlinks: Tuple["RelatedEntry", ...] = ()
    mentions: Tuple["RelatedEntry", ...] = ()

    @property
    def has_own_title(self) -> bool:
        return self.title != self.template.name


@dataclass(frozen=True)
class RelatedEntry:
    """Another entry shown on an entry's page: id, title, and where or how it is related."""

    id: str
    title: str
    detail: str
    excerpt: str = ""


def _related(store: Any, entry_id: str, templates: Mapping[str, Template], today: date, mentions: int) -> Tuple[Tuple[RelatedEntry, ...], Tuple[RelatedEntry, ...]]:
    try:
        about = store.about(entry_id, mentions=mentions)
    except Exception:  # the page shows anyway, without the links
        return (), ()
    backlinks, seen = [], set()
    for link in about.backlinks:
        if link.source in seen:
            continue
        seen.add(link.source)
        template = templates.get(link.source_template)
        when = short_date(link.source_day, today) if link.source_day else ""
        detail = " · ".join(part for part in (template.name if template else "", when, link.how) if part)
        backlinks.append(RelatedEntry(link.source, link.source_title, detail))
    named = []
    for hit in about.mentions:
        template = templates.get(hit.entry.template)
        detail = " · ".join(part for part in (template.name if template else "", short_date(hit.entry.day, today)) if part)
        named.append(RelatedEntry(hit.entry.id, hit.title, detail, hit.snippet.text if hit.snippet else ""))
    return tuple(backlinks), tuple(named)


def entry_detail(store: Any, entry_id: str, today: date, mentions: int = 10) -> EntryDetail:
    entry = store.get_entry(entry_id)
    template = store.get_template(entry.template)
    templates = {item.slug: item for item in store.list_templates()}
    blocks = []
    for spec in template.blocks:
        if spec.key not in entry.values:
            continue
        value = entry.values[spec.key]
        links: Tuple[Tuple[str, str], ...] = ()
        if spec.type == "link":
            found = []
            for linked_id in value:
                try:
                    linked = store.get_entry(linked_id)
                    linked_template = templates.get(linked.template)
                    found.append((linked_id, forms.entry_title(linked, linked_template, with_day=True) if linked_template else linked_id[:8]))
                except Exception:
                    found.append((linked_id, "voce non più presente"))
            links = tuple(found)
        blocks.append(
            DetailBlock(spec.key, spec.label, spec.type, spec.block_type.to_text(value, spec.options), value, dict(spec.options), links)
        )
    created, updated = local_timestamp(entry.created_at), local_timestamp(entry.updated_at)
    backlinks, named = _related(store, entry.id, templates, today, mentions)
    return EntryDetail(
        entry=entry,
        template=template,
        title=forms.entry_title(entry, template),
        day_label=italian_date(date.fromisoformat(entry.day)),
        created_label=created,
        updated_label=updated if updated != created else "",
        blocks=tuple(blocks),
        backlinks=backlinks,
        mentions=named,
    )


# * — Collezioni · Museion —


@dataclass(frozen=True)
class CollectionItem:
    id: str
    title: str
    subtitle: str
    status: str
    status_label: str
    fraction: Optional[float]
    counter: str
    rating: Optional[int]
    rating_max: int
    bookmark: str


@dataclass(frozen=True)
class CollectionGroup:
    slug: str
    name: str
    description: str
    icon: str
    color: str
    items: Tuple[CollectionItem, ...]

    @property
    def count_label(self) -> str:
        count = len(self.items)
        return "nessuna voce" if count == 0 else ("1 voce" if count == 1 else f"{count} voci")


def _first(template: Template, kind: str) -> Optional[BlockSpec]:
    return next((block for block in template.blocks if block.type == kind), None)


STATUS_ORDER = {"ongoing": 0, "paused": 1, "not_started": 2, "wishlist": 3, "completed": 4, "dropped": 5, "": 6}


def collection_item(entry: Entry, template: Template) -> CollectionItem:
    progress_spec, rating_spec, bookmark_spec = _first(template, "progress"), _first(template, "rating"), _first(template, "bookmark")
    progress = entry.values.get(progress_spec.key) if progress_spec else None
    status = progress.get("status", "") if progress else ""
    counter = ""
    if progress and "current" in progress:
        counter = forms.format_number(progress["current"])
        if "total" in progress:
            counter += f"/{forms.format_number(progress['total'])}"
        unit = progress_spec.options.get("unit") if progress_spec else ""
        if unit:
            counter += f" {unit}"
    subtitle_parts = []
    for spec in template.blocks:
        if spec.key == template.title_key or spec.type != "text" or spec.key not in entry.values:
            continue
        subtitle_parts.append(str(entry.values[spec.key]))
        break
    return CollectionItem(
        id=entry.id,
        title=forms.entry_title(entry, template),
        subtitle=" · ".join(subtitle_parts),
        status=status,
        status_label=PROGRESS_STATUSES.get(status, ""),
        fraction=forms.progress_fraction(progress),
        counter=counter,
        rating=entry.values.get(rating_spec.key) if rating_spec else None,
        rating_max=forms.rating_max(rating_spec) if rating_spec else 5,
        bookmark=str(entry.values.get(bookmark_spec.key, "")) if bookmark_spec else "",
    )


def build_collections(store: Any, category: str = "collezioni") -> List[CollectionGroup]:
    groups = []
    for template in store.list_templates(category=category):
        items = [collection_item(entry, template) for entry in store.list_entries(template=template.slug)]
        items.sort(key=lambda item: (STATUS_ORDER.get(item.status, 6), _plain(item.title)))
        groups.append(
            CollectionGroup(template.slug, template.name, template.description, template.icon, color_or(template.color), tuple(items))
        )
    groups.sort(key=lambda group: (-len(group.items), _plain(group.name)))
    return groups


# * — Modelli · Forme —

CATEGORY_LABELS: Dict[str, str] = {
    "diario": "Diario · Stoa",
    "collezioni": "Collezioni · Museion",
    "io": "Io · Delfi",
    "persone": "Persone · Agorà",
    "": "I tuoi modelli",
}
CATEGORY_ORDER = ("diario", "collezioni", "io", "persone")


@dataclass(frozen=True)
class TemplateRow:
    slug: str
    name: str
    description: str
    icon: str
    color: str
    category: str
    block_count: int
    entry_count: int
    from_pack: str

    @property
    def counts_label(self) -> str:
        blocks = "1 blocco" if self.block_count == 1 else f"{self.block_count} blocchi"
        entries = "nessuna voce" if self.entry_count == 0 else ("1 voce" if self.entry_count == 1 else f"{self.entry_count} voci")
        return f"{blocks} · {entries}"


def category_label(category: str) -> str:
    return CATEGORY_LABELS.get(category, category.capitalize() if category else CATEGORY_LABELS[""])


def group_templates(templates: Iterable[Template], counts: Mapping[str, int]) -> List[Tuple[str, List[TemplateRow]]]:
    groups: Dict[str, List[TemplateRow]] = {}
    for template in templates:
        row = TemplateRow(
            slug=template.slug,
            name=template.name,
            description=template.description,
            icon=template.icon,
            color=color_or(template.color),
            category=template.category,
            block_count=len(template.blocks),
            entry_count=counts.get(template.slug, 0),
            from_pack=template.origin.get("pack_id", ""),
        )
        groups.setdefault(template.category, []).append(row)
    order = {category: index for index, category in enumerate(CATEGORY_ORDER)}
    keys = sorted(groups, key=lambda category: (category == "", order.get(category, len(order)), category))
    return [(category_label(key), sorted(groups[key], key=lambda row: _plain(row.name))) for key in keys]


# * — the template editor —


@dataclass(frozen=True)
class OptionField:
    name: str
    label: str
    kind: str  # int, number, text, bool, list, numbers, template
    hint: str = ""


OPTION_FIELDS: Dict[str, Tuple[OptionField, ...]] = {
    "text": (OptionField("placeholder", "Esempio da mostrare", "text"), OptionField("max_length", "Lunghezza massima", "int", "300 di base")),
    "longtext": (OptionField("placeholder", "Esempio da mostrare", "text"), OptionField("max_length", "Lunghezza massima", "int", "50000 di base")),
    "number": (
        OptionField("unit", "Unità", "text", "pagine, ore, euro"),
        OptionField("min", "Minimo", "number"),
        OptionField("max", "Massimo", "number"),
        OptionField("integer", "Solo numeri interi", "bool"),
    ),
    "rating": (OptionField("max", "Stelle", "int", "da 3 a 10, 5 di base"),),
    "tags": (OptionField("suggestions", "Suggerimenti", "list", "separati da virgola"),),
    "date": (),
    "checklist": (OptionField("max_items", "Voci al massimo", "int", "100 di base"),),
    "scale": (
        OptionField("min", "Da", "int", "0 di base"),
        OptionField("max", "A", "int", "10 di base"),
        OptionField("low_label", "Etichetta in basso", "text", "per esempio: a terra"),
        OptionField("high_label", "Etichetta in alto", "text", "per esempio: al massimo"),
    ),
    "choice": (
        OptionField("choices", "Scelte", "list", "almeno 2, separate da virgola"),
        OptionField("values", "Punteggi", "numbers", "facoltativi, uno per scelta: 5, 4, 3"),
    ),
    "progress": (OptionField("unit", "Unità", "text", "pagine, episodi"), OptionField("total", "Totale", "int")),
    "bookmark": (OptionField("placeholder", "Esempio da mostrare", "text", "pag. 150"),),
    "link": (OptionField("template", "Solo voci del modello", "template"), OptionField("multiple", "Più collegamenti", "bool")),
}

REQUIRED_OPTIONS: Dict[str, Dict[str, Any]] = {
    "choice": {"choices": "Sì, No"},
}


def block_type_choices() -> List[Tuple[str, str, str]]:
    """(type, 'Aut-Aut · Scelta', description) for the 'add block' picker."""
    return [(name, forms.type_caption(name), block_type.description) for name, block_type in BLOCK_TYPES.items()]


def option_to_text(kind: str, value: Any) -> str:
    if value is None:
        return ""
    if kind == "bool":
        return "true" if value else ""
    if kind == "list":
        return ", ".join(str(item) for item in value)
    if kind == "numbers":
        return ", ".join(forms.format_number(item) for item in value)
    if kind in ("int", "number"):
        return forms.format_number(value)
    return str(value)


def option_from_text(field_spec: OptionField, text: str) -> Any:
    """None when blank; raises an Italian ValueError when it does not parse."""
    kind = field_spec.kind
    if kind == "bool":
        return True if str(text).strip().lower() in ("true", "1", "sì", "si", "yes") else None
    clean = (text or "").strip()
    if not clean:
        return None
    if kind in ("int", "number"):
        number = forms.parse_number_text(clean, field_spec.label)
        if kind == "int" and number != int(number):
            raise ValueError(f"{field_spec.label}: serve un numero intero")
        return int(number) if kind == "int" else number
    if kind == "list":
        return [part.strip() for part in clean.split(",") if part.strip()]
    if kind == "numbers":
        return [forms.parse_number_text(part, field_spec.label) for part in clean.split(",") if part.strip()]
    return clean


@dataclass
class EditorBlock:
    """One block while editing: options are kept as typed text until saving."""

    type: str
    label: str = ""
    key: str = ""  # empty for blocks not saved yet: the key comes from the label
    required: bool = False
    options: Dict[str, str] = field(default_factory=dict)
    help: str = ""

    @property
    def is_new(self) -> bool:
        return not self.key

    @property
    def caption(self) -> str:
        return forms.type_caption(self.type)


def new_editor_block(type_name: str) -> EditorBlock:
    if type_name not in BLOCK_TYPES:
        raise ValueError(f"tipo di blocco sconosciuto: '{type_name}'")
    defaults = {name: str(value) for name, value in REQUIRED_OPTIONS.get(type_name, {}).items()}
    return EditorBlock(type=type_name, options=defaults)


def editor_block_from_spec(spec: BlockSpec) -> EditorBlock:
    fields = {item.name: item for item in OPTION_FIELDS.get(spec.type, ())}
    options = {name: option_to_text(fields[name].kind if name in fields else "text", value) for name, value in spec.options.items()}
    if spec.type == "link" and "multiple" not in spec.options:
        options["multiple"] = "true"  # the core's default
    return EditorBlock(type=spec.type, label=spec.label, key=spec.key, required=spec.required, options=options, help=spec.help)


def unique_key(label: str, taken: Iterable[str]) -> str:
    taken = set(taken)
    base = slugify(label or "blocco")[:36].rstrip("_") or "blocco"
    if not SLUG.match(base):
        base = "b_" + base
    candidate, number = base, 2
    while candidate in taken:
        candidate = f"{base}_{number}"
        number += 1
    return candidate


def spec_from_editor(block: EditorBlock, taken: Iterable[str]) -> BlockSpec:
    """A validated BlockSpec; errors start with the block label."""
    name = block.label.strip() or forms.type_caption(block.type)
    options: Dict[str, Any] = {}
    for item in OPTION_FIELDS.get(block.type, ()):
        try:
            value = option_from_text(item, block.options.get(item.name, ""))
        except ValueError as error:
            raise ValueError(f"{name}: {error}") from None
        if value is not None:
            options[item.name] = value
    if block.type == "link" and "multiple" not in options:
        options["multiple"] = False
    spec = BlockSpec(
        key=block.key or unique_key(block.label, taken),
        type=block.type,
        label=block.label,
        required=block.required,
        options=options,
        help=block.help,
    )
    try:
        spec.validate()
    except ValueError as error:
        raise ValueError(f"{name}: {error}") from None
    return spec


@dataclass
class EditorState:
    name: str = ""
    description: str = ""
    category: str = ""
    icon: str = ""
    color: str = ""
    blocks: List[EditorBlock] = field(default_factory=list)
    slug: str = ""  # empty for a new template
    title_block: str = ""
    origin: Dict[str, str] = field(default_factory=dict)
    version: int = 1

    @property
    def is_new(self) -> bool:
        return not self.slug


def editor_from_template(template: Template) -> EditorState:
    return EditorState(
        name=template.name,
        description=template.description,
        category=template.category,
        icon=template.icon,
        color=template.color,
        blocks=[editor_block_from_spec(spec) for spec in template.blocks],
        slug=template.slug,
        title_block=template.title_block,
        origin=dict(template.origin),
        version=template.version,
    )


def template_from_editor(state: EditorState, slug: str) -> Template:
    """Build and validate the template; `slug` is the final one (free for a new template)."""
    if not state.name.strip():
        raise ValueError("dai un nome al modello")
    if not state.blocks:
        raise ValueError("aggiungi almeno un blocco")
    specs: List[BlockSpec] = []
    taken = [block.key for block in state.blocks if block.key]
    for block in state.blocks:
        if not block.label.strip():
            raise ValueError(f"il blocco {forms.type_caption(block.type)} non ha un'etichetta")
        spec = spec_from_editor(block, taken)
        taken.append(spec.key)
        specs.append(spec)
    keys = [spec.key for spec in specs]
    template = Template(
        slug=slug,
        name=state.name,
        blocks=specs,
        description=state.description,
        icon=state.icon,
        color=state.color,
        category=state.category,
        title_block=state.title_block if state.title_block in keys else "",
        origin=dict(state.origin),
        version=state.version,
    )
    return template.validate()


def move_block(blocks: Sequence[EditorBlock], index: int, delta: int) -> List[EditorBlock]:
    result = list(blocks)
    target = index + delta
    if 0 <= index < len(result) and 0 <= target < len(result):
        result[index], result[target] = result[target], result[index]
    return result


def entries_broken_by(store: Any, template: Template) -> int:
    """How many saved entries would no longer be valid with this version of the template."""
    broken = 0
    for entry in store.list_entries(template=template.slug):
        try:
            validate_values(template, entry.values)
        except ValueError:
            broken += 1
    return broken


TEMPLATE_ICONS: Tuple[str, ...] = (
    "ARTICLE_OUTLINED", "EDIT_NOTE", "PSYCHOLOGY", "LIGHTBULB_OUTLINE", "MENU_BOOK", "MOVIE", "TV", "MUSIC_NOTE",
    "SPORTS_ESPORTS", "FITNESS_CENTER", "RESTAURANT", "FLIGHT", "PETS", "PERSON", "GROUPS", "WORK_OUTLINE",
    "SCHOOL_OUTLINED", "SAVINGS_OUTLINED", "FAVORITE_BORDER", "STAR", "LOCAL_FLORIST", "CHECKLIST", "EVENT", "AUTO_STORIES",
)
TEMPLATE_COLORS: Tuple[str, ...] = (ACCENT,) + CATEGORICAL


# * — Scuole: built-in packs —

ACTION_LABELS: Dict[str, str] = {"new": "nuovo", "update": "aggiornamento", "same": "già installato", "copy": "copia"}
ACTION_COLORS: Dict[str, str] = {"new": ACCENT, "update": "#FF5500", "same": TEXT_DIM, "copy": "#FF007F"}


@dataclass(frozen=True)
class PackCard:
    id: str
    name: str
    description: str
    version: str
    template_names: Tuple[str, ...]
    installed: int

    @property
    def installed_label(self) -> str:
        total = len(self.template_names)
        if self.installed == 0:
            return f"{total} modelli, nessuno installato"
        if self.installed >= total:
            return f"tutti i {total} modelli installati"
        return f"{self.installed} di {total} modelli installati"


def pack_card(pack: Pack, installed_slugs: Iterable[str]) -> PackCard:
    installed = set(installed_slugs)
    return PackCard(
        id=pack.id,
        name=pack.name,
        description=pack.description,
        version=pack.version,
        template_names=tuple(template.name for template in pack.templates),
        installed=sum(1 for template in pack.templates if template.slug in installed),
    )


@dataclass(frozen=True)
class PlanRow:
    template_name: str
    target_slug: str
    action: str
    action_label: str
    reason: str
    color: str


def plan_rows(plan: InstallPlan) -> List[PlanRow]:
    return [
        PlanRow(
            step.template.name,
            step.target_slug,
            step.action,
            ACTION_LABELS.get(step.action, step.action),
            step.reason,
            ACTION_COLORS.get(step.action, ACCENT),
        )
        for step in plan.steps
    ]


def plan_summary(plan: InstallPlan) -> str:
    counts = plan.summary()
    words = {
        "new": ("nuovo", "nuovi"),
        "update": ("aggiornamento", "aggiornamenti"),
        "copy": ("copia", "copie"),
        "same": ("già installato", "già installati"),
    }
    parts = []
    for action in ("new", "update", "copy", "same"):
        count = counts.get(action, 0)
        if count:
            singular, plural = words[action]
            parts.append(f"{count} {singular if count == 1 else plural}")
    return ", ".join(parts) or "niente da installare"


def plan_has_changes(plan: InstallPlan) -> bool:
    return any(step.action != "same" for step in plan.steps)


def export_path(folder: Path, name: str, now: datetime) -> Path:
    return folder / "exports" / f"{slugify(name or 'modelli')}-{now:%Y%m%d-%H%M%S}.zbpack.json"


def export_templates(store: Any, folder: Path, slugs: Sequence[str], name: str, now: datetime, author: str = "") -> Path:
    """Write the chosen templates (structure only, never entries) to `exports/`."""
    if not slugs:
        raise ValueError("scegli almeno un modello da esportare")
    templates = [store.get_template(slug) for slug in slugs]
    label = (name or "").strip() or "I miei modelli"
    pack = build_pack(templates, pack_id=f"personale.{slugify(label)}"[:80], name=label, author=author)
    path = export_path(folder, label, now)
    path.parent.mkdir(parents=True, exist_ok=True)
    return write_pack_file(pack, path)


# * — Organon: Daimon (reminders) —


@dataclass
class MomentForm:
    key: str
    label: str
    enabled: bool
    time: str
    weekdays: List[int]


@dataclass
class ReminderForm:
    enabled: bool
    moments: List[MomentForm]
    quiet_enabled: bool
    quiet_start: str
    quiet_end: str


def reminder_form(config: ReminderConfig) -> ReminderForm:
    return ReminderForm(
        enabled=config.enabled,
        moments=[MomentForm(moment.key, moment.label, moment.enabled, moment.time, list(moment.weekdays)) for moment in config.moments],
        quiet_enabled=config.quiet_hours.enabled,
        quiet_start=config.quiet_hours.start,
        quiet_end=config.quiet_hours.end,
    )


def config_from_reminder_form(form: ReminderForm, base: ReminderConfig) -> ReminderConfig:
    """A validated ReminderConfig; the core's Italian ValueError when something is off."""
    moments = []
    for item in form.moments:
        previous = base.moment(item.key)
        moments.append(
            MomentConfig(
                key=item.key,
                enabled=bool(item.enabled),
                time=item.time,
                weekdays=tuple(sorted(set(item.weekdays))),
                backoff_dismissed_on=previous.backoff_dismissed_on,
            )
        )
    quiet = QuietHours(enabled=bool(form.quiet_enabled), start=form.quiet_start, end=form.quiet_end)
    return replace(base, enabled=bool(form.enabled), moments=tuple(moments), quiet_hours=quiet)


def toggle_weekday(weekdays: Sequence[int], day: int) -> List[int]:
    days = set(weekdays)
    days.symmetric_difference_update({day})
    return sorted(days)


WEEKDAY_SHORT = WEEKDAY_NAMES


# * — Organon: Parresia, Mnemosyne, Le Nuvole, Informazioni —


def consent_label(status: Mapping[str, Any]) -> str:
    if not status:
        return "non ancora data"
    when = local_timestamp(status.get("decided_at", ""))
    version = status.get("notice_version", "?")
    if status.get("accepted"):
        return f"accettata il {when} (informativa versione {version})"
    return f"rifiutata il {when}"


@dataclass(frozen=True)
class SnapshotRow:
    id: str
    when: str
    reason: str
    size: str
    encrypted: bool
    note: str
    problem: str


def snapshot_rows(snapshots: Iterable[Any]) -> List[SnapshotRow]:
    """Rows for the Mnemosyne list; tolerant of missing attributes."""
    from zibaldone.storage.paths import human_size

    rows = []
    for item in snapshots:
        created = getattr(item, "created_at", None)
        if isinstance(created, datetime):
            moment = created.astimezone() if created.tzinfo else created.replace(tzinfo=timezone.utc).astimezone()
            when = f"{moment.day} {MONTHS_SHORT[moment.month - 1]} {moment.year}, {moment:%H:%M}"
        else:
            when = str(created or "")
        rows.append(
            SnapshotRow(
                id=str(getattr(item, "id", "")),
                when=when,
                reason=str(getattr(item, "reason_label", "") or getattr(item, "reason", "")),
                size=human_size(int(getattr(item, "size", 0) or 0)),
                encrypted=bool(getattr(item, "encrypted", False)),
                note=str(getattr(item, "note", "") or ""),
                problem=str(getattr(item, "problem", "") or ""),
            )
        )
    return rows


@dataclass(frozen=True)
class MascotCard:
    name: str
    animal: str
    area: str
    philosopher: str
    story: str
    color: str
    is_app: bool


def mascot_cards() -> List[MascotCard]:
    return [
        MascotCard(
            mascot.name,
            mascot.animal,
            "l'app" if mascot.sphere == "app" else mascot.sphere,
            mascot.philosopher,
            mascot.story,
            mascot.color,
            mascot.sphere == "app",
        )
        for mascot in MASCOTS
    ]


# * — Rizoma: the graph (0.1.3) —

GRAPH_LABEL_CHARS = 18
GRAPH_ALL_LABELS_UP_TO = 30  # with more nodes, only the most connected ones get a name
GRAPH_HUB_LABELS = 12
GRAPH_EDGE_COLORS = {"block": "#3B6E8F", "wiki": "#5C5F8A", "shared_tag": "#4A4D66", "tag": "#4A4D66", "template": "#4A4D66"}


@dataclass
class GraphQuery:
    """Filters of the Rizoma screen (kept between visits)."""

    template: str = ""
    isolated: bool = True
    unresolved: bool = False
    depth: int = 1


def load_graph(store: Any, query: GraphQuery, around: str = "") -> Any:
    """The graph for the screen; `around` (an entry id) keeps only its neighbourhood."""
    from zibaldone.core.graph import GraphFilters, graph_from_store

    filters = GraphFilters(
        templates=(query.template,) if query.template else (),
        around=around or None,
        depth=max(1, min(int(query.depth), 3)),
        unresolved=query.unresolved,
        isolated=query.isolated,
    )
    return graph_from_store(store, filters)


@dataclass(frozen=True)
class DrawnNode:
    id: str
    kind: str
    x: float
    y: float
    radius: float
    color: str
    label: str  # "" when the name would clutter the picture
    title: str  # always the full name, for taps and lists
    center: bool = False


@dataclass(frozen=True)
class DrawnEdge:
    x1: float
    y1: float
    x2: float
    y2: float
    color: str
    width: float


@dataclass(frozen=True)
class GraphDrawing:
    width: float
    height: float
    nodes: Tuple[DrawnNode, ...]
    edges: Tuple[DrawnEdge, ...]


def _short(text: str, limit: int = GRAPH_LABEL_CHARS) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def draw_graph(graph: Any, width: float, height: float, around: str = "", margin: float = 26) -> GraphDrawing:
    """Pixel positions for a canvas of this size (the layout itself is in 0..1)."""
    width, height = max(float(width), 2 * margin + 1), max(float(height), 2 * margin + 1)
    usable_w, usable_h = width - 2 * margin, height - 2 * margin
    labelled = {node.id for node in graph.nodes} if len(graph.nodes) <= GRAPH_ALL_LABELS_UP_TO else {
        node.id for node in sorted(graph.nodes, key=lambda node: (-node.degree, node.label))[:GRAPH_HUB_LABELS] if node.degree > 0
    }
    labelled.add(around)
    nodes, where = [], {}
    for node in graph.nodes:
        x, y = margin + node.x * usable_w, margin + node.y * usable_h
        where[node.id] = (x, y)
        radius = min(14.0, 5.0 + 2.0 * math.sqrt(max(node.degree, 0)))
        color = TEXT_DIM if node.kind == "missing" else (node.color or ACCENT)
        nodes.append(
            DrawnNode(node.id, node.kind, x, y, radius + (3 if node.id == around else 0), color, _short(node.label) if node.id in labelled else "", node.label, node.id == around)
        )
    edges = []
    for edge in graph.edges:
        if edge.source not in where or edge.target not in where:
            continue
        (x1, y1), (x2, y2) = where[edge.source], where[edge.target]
        edges.append(DrawnEdge(x1, y1, x2, y2, GRAPH_EDGE_COLORS.get(edge.kind, "#4A4D66"), min(4.0, 1.0 + 0.5 * (edge.weight - 1))))
    return GraphDrawing(width, height, tuple(nodes), tuple(edges))


def nearest_node(drawing: GraphDrawing, x: float, y: float, slack: float = 14) -> Optional[DrawnNode]:
    """The node under a tap, with some room for fingers; None when the tap is on empty space."""
    best, best_distance = None, None
    for node in drawing.nodes:
        distance = math.hypot(node.x - x, node.y - y)
        if distance <= node.radius + slack and (best_distance is None or distance < best_distance):
            best, best_distance = node, distance
    return best


def graph_summary(graph: Any) -> str:
    facts = graph.facts
    if not facts.entries:
        return "nessuna voce"
    parts = ["1 voce" if facts.entries == 1 else f"{facts.entries} voci", "1 collegamento" if facts.edges == 1 else f"{facts.edges} collegamenti"]
    if facts.components > 1:
        parts.append(f"{facts.components} gruppi")
    return ", ".join(parts)


# * — Theoria: statistics and reviews (0.1.4) —


@dataclass
class StatsQuery:
    """Which period the Statistiche screen shows (kept between visits)."""

    kind: str = "week"  # "week" or "month"
    day: str = ""  # any day of the period, ISO; "" = today


def stats_day(query: StatsQuery, today: date) -> date:
    try:
        return date.fromisoformat(query.day) if query.day else today
    except ValueError:
        return today


def load_stats(store: Any, query: StatsQuery, today: date) -> Any:
    """The `core.stats.Review` of the chosen week or month."""
    from zibaldone.core.stats import review

    templates = {template.slug: template for template in store.list_templates()}
    kind = "month" if query.kind == "month" else "week"
    return review(store.list_entries(newest_first=False), templates, store.all_links(), kind, stats_day(query, today), today)


def move_period(query: StatsQuery, today: date, step: int) -> bool:
    """Go to the previous (-1) or next (+1) period; never past the current one. True when it moved."""
    from zibaldone.core.stats import period_of

    period = period_of("month" if query.kind == "month" else "week", stats_day(query, today))
    target = period.previous() if step < 0 else period.next()
    if target.start > today:
        return False
    query.day = "" if target.contains(today) else target.start.isoformat()
    return True


def mood_point_label(point: Any) -> str:
    from zibaldone.core.stats import short_day

    if point.start == point.end:
        return short_day(point.start)
    return f"sett. {point.start.isocalendar()[1]} ({point.start.day}/{point.start.month}–{point.end.day}/{point.end.month})"


def writing_line(result: Any) -> str:
    period, activity = result.period, result.activity
    if not result.activity.total:
        return "Nessuna voce in questo periodo."
    previous = f"la {period.noun} prima" if period.kind == "week" else f"il {period.noun} prima"
    entries = "1 voce" if activity.total == 1 else f"{activity.total} voci"
    days = "1 giorno" if activity.active_days == 1 else f"{activity.active_days} giorni"
    return f"{entries} in {days} su {activity.days} ({previous}: {result.previous_entries})."


def prepare_review(store: Any, kind: str, day: date, today: date) -> Tuple[Optional[Entry], bool]:
    """The review entry of the period: (entry, True) when just written from the proposal,
    (entry, False) when one already exists, (None, False) when no review template is installed."""
    from zibaldone.core.stats import in_period, propose_review_values, review, review_slugs, review_template

    kind = "month" if kind == "month" else "week"
    templates = {template.slug: template for template in store.list_templates()}
    target = review_template(templates, kind)
    if target is None:
        return None, False
    result = review(store.list_entries(newest_first=False), templates, store.all_links(), kind, day, today, exclude_templates=sorted(set(review_slugs(templates)) | {target.slug}))
    existing = in_period(store.list_entries(template=target.slug), result.period)
    if existing:
        return existing[0], False
    when = min(result.period.end, today) if result.period.start <= today else result.period.end
    return store.add_entry(target.slug, propose_review_values(result, target), when.isoformat()), True
