"""Agorà (0.2.1): the people of one's life, in every area.

A person is an entry of a person template ("L'Altro", slug `persona`): name,
nicknames, bond and roles (`core/roles.py`, which also give the person's
areas), contacts, birthday and how often one would like to hear from them.
Every entry of a meeting template ("Simposio", slug `incontro`) that links the
person is a contact with them: a call, messages, a dinner. From those come
the last contact, the rhythm and who it may be nice to hear from again.

"Tutto di Marco" groups every entry that links or names a person by the
life area of that entry.

Pure functions over entries and templates, with `today` always passed in;
the helpers at the end write through a Store.
"""

import calendar
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from zibaldone.core.areas import AREA_LIST, area_label, entry_areas
from zibaldone.core.links import PERSON_CATEGORIES, alias_blocks, is_person_template, name_key
from zibaldone.core.roles import bond_of, roles_of
from zibaldone.core.stats import entry_date, is_mood_block, mood_score
from zibaldone.core.templates import Entry, Template

PERSON_TEMPLATE = "persona"
MEETING_TEMPLATE = "incontro"
PEOPLE_PACK_NAME = "persone"
KIND_BLOCK = "tipo"
NOTE_BLOCK = "cosa"
TITLE_BLOCK = "titolo"
PHONE_BLOCK = "telefono"
EMAIL_BLOCK = "email"
SOCIAL_BLOCK = "social"
BIRTHDAY_BLOCK = "compleanno"
FREQUENCY_BLOCK = "frequenza"
NOTES_BLOCK = "note"
# Links between people (0.2.2, `core/relations.py`): block key → what the linked people are to this one.
RELATION_BLOCKS: Dict[str, str] = {"genitori": "genitore", "fratelli": "fratello", "colleghi": "collega", "conosce": "conosce"}
RHYTHM_CONTACTS = 10  # the rhythm is the average gap between the last ones
NO_AREA = ""

# "Ogni quanto sentirvi" → days.
FREQUENCIES: Dict[str, int] = {
    "ogni settimana": 7,
    "ogni due settimane": 14,
    "ogni mese": 30,
    "ogni tre mesi": 91,
    "ogni sei mesi": 182,
    "ogni anno": 365,
}

# How a contact went (the `tipo` choice of Simposio) → Flet icon name.
CONTACT_KINDS: Dict[str, str] = {
    "Di persona": "PEOPLE",
    "Uscita": "LOCAL_CAFE",
    "Visita": "HOME",
    "Chiamata": "CALL",
    "Videochiamata": "VIDEOCAM",
    "Messaggi": "CHAT",
    "Evento": "CELEBRATION",
    "Altro": "MORE_HORIZ",
}
CONTACT_ICON = "GROUPS"
CONTACT_LABEL = "Incontro"  # contacts written before 0.2.1 have no kind
QUICK_KINDS = ("Chiamata", "Messaggi", "Di persona")


def ago(days: Optional[int]) -> str:
    """'oggi', 'ieri', '5 giorni fa', '3 settimane fa', '2 mesi fa', 'più di un anno fa'; 'mai' for None."""
    if days is None:
        return "mai"
    if days <= 0:
        return "oggi"
    if days == 1:
        return "ieri"
    if days < 14:
        return f"{days} giorni fa"
    if days < 60:
        return f"{days // 7} settimane fa"
    if days < 365:
        return f"{days // 30} mesi fa"
    return "un anno fa" if days < 730 else f"{days // 365} anni fa"


def every_text(days: float) -> str:
    """An average gap in words: 'ogni 4 giorni', 'ogni 2 settimane', 'ogni mese'."""
    rounded = max(1, round(days))
    if rounded == 1:
        return "ogni giorno"
    if rounded < 11:
        return f"ogni {rounded} giorni"
    if rounded < 45:
        weeks = round(rounded / 7)
        return "ogni settimana" if weeks <= 1 else f"ogni {weeks} settimane"
    months = round(rounded / 30)
    return "ogni mese" if months <= 1 else f"ogni {months} mesi"


# * — templates —


def is_meeting_template(template: Optional[Template]) -> bool:
    """A template of moments with people ("Simposio"): it links to people and is not a person itself."""
    if template is None or is_person_template(template):
        return False
    if template.slug.split("_")[0] == MEETING_TEMPLATE:
        return True
    return template.category in PERSON_CATEGORIES and any(spec.type == "link" for spec in template.blocks)


def _text(entry: Entry, key: str) -> str:
    value = entry.values.get(key)
    return value if isinstance(value, str) else ""


def _day(entry: Entry, key: str) -> Optional[date]:
    try:
        return date.fromisoformat(_text(entry, key))
    except ValueError:
        return None


# * — people and their contacts —


@dataclass(frozen=True)
class Contact:
    """A meeting entry that links the person."""

    entry_id: str
    day: date
    kind: str
    title: str
    note: str = ""
    mood: Optional[float] = None  # 1–5 from the meeting's mood block (Umore)

    @property
    def label(self) -> str:
        return self.kind or CONTACT_LABEL

    @property
    def icon(self) -> str:
        return CONTACT_KINDS.get(self.kind, CONTACT_ICON)


@dataclass
class Person:
    entry: Entry
    name: str
    nicknames: List[str]
    bond: str
    roles: List[str]
    areas: List[str]
    phone: str = ""
    email: str = ""
    social: List[str] = field(default_factory=list)
    birthday: Optional[date] = None
    frequency: str = ""
    note: str = ""
    contacts: List[Contact] = field(default_factory=list)  # newest first
    relations: Dict[str, List[str]] = field(default_factory=dict)  # relation block key → linked person ids

    @property
    def id(self) -> str:
        return self.entry.id

    @property
    def short_id(self) -> str:
        return self.entry.short_id

    @property
    def main_area(self) -> str:
        return self.areas[0] if self.areas else ""

    @property
    def frequency_days(self) -> Optional[int]:
        return FREQUENCIES.get(self.frequency.lower()) if self.frequency else None

    @property
    def last_contact(self) -> Optional[date]:
        return self.contacts[0].day if self.contacts else None

    def days_since(self, today: date) -> Optional[int]:
        last = self.last_contact
        return None if last is None else max(0, (today - last).days)

    def is_due(self, today: date) -> bool:
        """It would be nice to hear from them: their rhythm is set and the time has passed."""
        wanted = self.frequency_days
        if wanted is None:
            return False
        since = self.days_since(today)
        return since is None or since >= wanted

    def overdue(self, today: date) -> int:
        """Days beyond the wished rhythm (a large number when never heard)."""
        wanted, since = self.frequency_days, self.days_since(today)
        if wanted is None:
            return 0
        return 10_000 if since is None else since - wanted

    @property
    def rhythm(self) -> Optional[float]:
        """Average days between the last contacts (None with fewer than 2 days)."""
        days = sorted({contact.day for contact in self.contacts}, reverse=True)[:RHYTHM_CONTACTS]
        if len(days) < 2:
            return None
        return (days[0] - days[-1]).days / (len(days) - 1)

    @property
    def role_line(self) -> str:
        """'Famiglia · madre' or 'collega, socio' or ''."""
        roles = [role for role in self.roles if role.lower() != self.bond.lower()]
        parts = ([self.bond] if self.bond else []) + ([", ".join(roles)] if roles else [])
        return " · ".join(parts)

    def contact_line(self, today: date) -> str:
        """'sentiti ieri (chiamata)', 'mai sentiti'."""
        since = self.days_since(today)
        if since is None:
            return "mai sentiti"
        return f"sentiti {ago(since)} ({self.contacts[0].label.lower()})"

    def rhythm_line(self, today: date) -> str:
        """The wished rhythm and how it is going, in neutral words."""
        parts = []
        if self.frequency:
            parts.append(f"vorresti sentirvi {self.frequency.lower()}")
        if self.rhythm is not None:
            parts.append(f"di solito vi sentite {every_text(self.rhythm)}")
        if self.is_due(today):
            parts.append("potrebbe essere il momento di farsi vivi")
        return "; ".join(parts)


def person_from(entry: Entry, template: Template, contacts: Sequence[Contact] = ()) -> Person:
    nicknames: List[str] = []
    for key in alias_blocks(template):
        nicknames += [nick for nick in entry.values.get(key, []) if isinstance(nick, str)]
    social = entry.values.get(SOCIAL_BLOCK, [])
    return Person(
        entry=entry,
        name=entry.title(template),
        nicknames=nicknames,
        bond=bond_of(entry, template),
        roles=roles_of(entry, template),
        areas=entry_areas(entry, template),
        phone=_text(entry, PHONE_BLOCK),
        email=_text(entry, EMAIL_BLOCK),
        social=[item for item in social if isinstance(item, str)] if isinstance(social, list) else [],
        birthday=_day(entry, BIRTHDAY_BLOCK),
        frequency=_text(entry, FREQUENCY_BLOCK),
        note=_text(entry, NOTES_BLOCK),
        contacts=sorted(contacts, key=lambda contact: (contact.day, contact.entry_id), reverse=True),
        relations={
            spec.key: [ref for ref in entry.values.get(spec.key, []) if isinstance(ref, str) and ref != entry.id]
            for spec in template.blocks
            if spec.type == "link" and spec.key in RELATION_BLOCKS
        },
    )


def meeting_people(entry: Entry, template: Template) -> List[str]:
    """Ids linked by the meeting's link blocks, in order."""
    found: List[str] = []
    for spec in template.blocks:
        if spec.type == "link":
            found += [ref for ref in entry.values.get(spec.key, []) if isinstance(ref, str) and ref not in found]
    return found


def contact_of(entry: Entry, template: Template) -> Contact:
    kind = _text(entry, KIND_BLOCK)
    moods = [mood_score(spec, entry.values.get(spec.key)) for spec in template.blocks if is_mood_block(spec)]
    mood = next((value for value in moods if value is not None), None)
    return Contact(entry.id, entry_date(entry), kind, entry.title(template), _text(entry, NOTE_BLOCK), mood)


def people_from(entries: Iterable[Entry], templates: Mapping[str, Template]) -> List[Person]:
    """Every person with their contacts, by name."""
    entries = list(entries)
    contacts: Dict[str, List[Contact]] = {}
    for entry in entries:
        template = templates.get(entry.template)
        if is_meeting_template(template):
            contact = contact_of(entry, template)
            for ref in meeting_people(entry, template):
                contacts.setdefault(ref, []).append(contact)
    people = []
    for entry in entries:
        template = templates.get(entry.template)
        if template is not None and is_person_template(template):
            people.append(person_from(entry, template, contacts.get(entry.id, [])))
    return sorted(people, key=lambda person: (person.name.casefold(), person.id))


def find_person(people: Sequence[Person], text: str) -> Optional[Person]:
    """By id (at least 4 characters), name or nickname, or a unique start of a name."""
    wanted = name_key(text)
    if not wanted:
        return None
    if len(wanted) >= 4 and all(char in "0123456789abcdef" for char in wanted):
        by_id = [person for person in people if person.id.startswith(wanted)]
        if len(by_id) == 1:
            return by_id[0]
    for person in people:
        if wanted == name_key(person.name) or wanted in (name_key(nick) for nick in person.nicknames):
            return person
    starts = [person for person in people if name_key(person.name).startswith(wanted)]
    return starts[0] if len(starts) == 1 else None


def people_in_area(people: Iterable[Person], area: str) -> List[Person]:
    return [person for person in people if area in person.areas]


def due_people(people: Iterable[Person], today: date) -> List[Person]:
    """People it would be nice to hear from, the longest overdue first."""
    due = [person for person in people if person.is_due(today)]
    return sorted(due, key=lambda person: (-person.overdue(today), person.name.casefold()))


# * — "tutto di Marco" —


@dataclass(frozen=True)
class Occasion:
    """A date to remember: for now the birthday, `kind` leaves room for anniversaries."""

    person_id: str
    name: str
    kind: str
    day: date
    in_days: int  # 0 = today
    turning: Optional[int]  # the age reached, when the birth year is a believable one


def _on_year(day: date, year: int) -> date:
    """The same day in `year`; 29 February falls on the 28th in a year that is not a leap one."""
    if day.month == 2 and day.day == 29 and not calendar.isleap(year):
        return date(year, 2, 28)
    return date(year, day.month, day.day)


def occasions(people: Iterable[Person], today: date, days: int = 30) -> List[Occasion]:
    """The birthdays from today to `days` days ahead, soonest first."""
    found = []
    for person in people:
        if person.birthday is None:
            continue
        coming = _on_year(person.birthday, today.year)
        if coming < today:
            coming = _on_year(person.birthday, today.year + 1)
        if (coming - today).days > days:
            continue
        age = coming.year - person.birthday.year
        found.append(Occasion(person.id, person.name, "compleanno", coming, (coming - today).days, age if 0 < age <= 130 else None))
    return sorted(found, key=lambda item: (item.day, item.name.casefold(), item.person_id))


@dataclass(frozen=True)
class Related:
    """An entry that links or names the person."""

    entry: Entry
    title: str
    template_name: str
    how: str


@dataclass
class AreaGroup:
    area: str  # '' for the entries without an area
    label: str
    items: List[Related]


def group_by_area(related: Iterable[Tuple[Entry, Template, str]]) -> List[AreaGroup]:
    """Entries grouped by their areas (one entry can sit in more groups), newest first in each."""
    groups: Dict[str, List[Related]] = {}
    seen: Dict[str, set] = {}
    for entry, template, how in related:
        item = Related(entry, entry.title(template), template.name, how)
        for area in entry_areas(entry, template) or [NO_AREA]:
            if entry.id in seen.setdefault(area, set()):
                continue
            seen[area].add(entry.id)
            groups.setdefault(area, []).append(item)
    ordered = [area.key for area in AREA_LIST if area.key in groups] + ([NO_AREA] if NO_AREA in groups else [])
    return [
        AreaGroup(area, area_label(area) if area else "Senza area", sorted(groups[area], key=lambda item: (item.entry.day, item.entry.created_at), reverse=True))
        for area in ordered
    ]


@dataclass
class PersonPage:
    person: Person
    groups: List[AreaGroup]
    mentions: List[Any]  # search hits naming the person without a link
    total: int


def person_page(store: Any, person: Person, mentions: int = 20) -> PersonPage:
    """Everything about a person, by area: who links them, what they link, who names them."""
    about = store.about(person.id, mentions=mentions)
    templates = {template.slug: template for template in store.list_templates()}
    related: List[Tuple[Entry, Template, str]] = []
    seen = set()
    # Other people (relatives, colleagues) are in the person's Legami, not here.
    for info in about.backlinks:
        if info.source in seen:
            continue
        seen.add(info.source)
        entry = store.get_entry(info.source)
        template = templates.get(entry.template)
        if template is not None and not is_person_template(template):
            related.append((entry, template, info.how))
    for info in about.outgoing:
        if info.target is None or info.target in seen:
            continue
        seen.add(info.target)
        entry = store.get_entry(info.target)
        template = templates.get(entry.template)
        if template is not None and not is_person_template(template):
            related.append((entry, template, f"collegata da «{info.block_label}»"))
    hits = [hit for hit in about.mentions if hit.entry.id not in seen]
    return PersonPage(person, group_by_area(related), hits, len(related) + len(hits))


# * — writing through a Store —


class PeopleError(ValueError):
    """A people action cannot run (for example the people pack is missing)."""


def meeting_template_of(store: Any) -> Template:
    template = store.find_template(MEETING_TEMPLATE)
    if template is None:
        raise PeopleError(f"manca il modello '{MEETING_TEMPLATE}': installa la Scuola «Agorà · Persone» (`zbone pack install {PEOPLE_PACK_NAME}`)")
    return template


CONTACT_TITLES = {
    "Chiamata": "Chiamata con {name}",
    "Videochiamata": "Videochiamata con {name}",
    "Messaggi": "Messaggi con {name}",
    "Uscita": "Uscita con {name}",
    "Visita": "Visita a {name}",
    "Evento": "Evento con {name}",
}


def contact_title(kind: str, name: str) -> str:
    return CONTACT_TITLES.get(kind, "Con {name}").format(name=name)


def log_contact(store: Any, person: Person, kind: str = "", note: str = "", day: Optional[str] = None, title: str = "") -> Entry:
    """Write that you heard from someone: a Simposio entry linking them, in their main area."""
    template = meeting_template_of(store)
    specs = {spec.key: spec for spec in template.blocks}
    link_keys = [spec.key for spec in template.blocks if spec.type == "link"]
    if not link_keys or TITLE_BLOCK not in specs:
        raise PeopleError(f"il modello «{template.name}» non ha i blocchi per un incontro (titolo e con chi)")
    values: Dict[str, Any] = {link_keys[0]: [person.id]}
    if kind:
        spec = specs.get(KIND_BLOCK)
        if spec is None:
            raise PeopleError(f"il modello «{template.name}» non ha il blocco «Come»: reinstalla Agorà · Persone")
        try:
            kind = values[KIND_BLOCK] = spec.block_type.normalize(kind, spec.options)
        except ValueError as error:
            raise PeopleError(f"{spec.label}: {error}") from None
    values[TITLE_BLOCK] = title.strip() or contact_title(kind, person.name)
    if note and note.strip() and NOTE_BLOCK in specs:
        values[NOTE_BLOCK] = note
    area = person.main_area if person.main_area and person.main_area != template.area else None
    return store.add_entry(template.slug, values, day=day, area=area)


def load_people(store: Any) -> List[Person]:
    templates = {template.slug: template for template in store.list_templates()}
    return people_from(store.list_entries(newest_first=False), templates)
