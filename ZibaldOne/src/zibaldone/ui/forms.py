"""The entry form without Flet: what each control holds, and how it becomes entry values.

Each block type has a *state*, the plain data its control edits:

- text, longtext, bookmark, number, date: the text in the field (`str`);
- rating, scale: `int` or None (not given yet);
- choice: the chosen label or None;
- tags: `{"tags": [...], "text": "what is still being typed"}`;
- checklist: `[{"text": ..., "done": bool}, ...]`;
- progress: `{"status": key or None, "current": "text", "total": "text"}`;
- link: a list of entry ids.

`collect_values` turns the states into values and checks them with the core
(`BlockType.normalize`, `validate_values`), keeping the core's Italian messages
next to the field they belong to.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from zibaldone.core.blocks import BLOCK_TYPES, PROGRESS_STATUSES, BlockType, is_number, parse_day
from zibaldone.core.templates import BlockSpec, Entry, Template, validate_values

REQUIRED_MESSAGE = "questo blocco è obbligatorio"
FORM_KEY = "_form"
DAY_KEY = "_day"

HINTS: Dict[str, str] = {
    "text": "",
    "longtext": "",
    "number": "un numero, con la virgola o il punto",
    "rating": "tocca una stella; di nuovo per toglierla",
    "tags": "separale con una virgola",
    "date": "",
    "checklist": "una voce per riga",
    "scale": "",
    "choice": "",
    "progress": "",
    "bookmark": "per esempio pag. 150, S02E05, capitolo 7",
    "link": "scegli tra le voci già scritte",
}


def type_caption(type_name: str) -> str:
    """'Aut-Aut · Scelta': the philosophical nickname with the plain label."""
    block_type = BLOCK_TYPES.get(type_name)
    if block_type is None:
        return type_name
    return f"{block_type.nickname} · {block_type.label}"


def field_label(spec: BlockSpec) -> str:
    return f"{spec.label} *" if spec.required else spec.label


def field_hint(spec: BlockSpec) -> str:
    if spec.help:
        return spec.help
    if spec.type in ("text", "bookmark") and spec.options.get("placeholder"):
        return str(spec.options["placeholder"])
    return HINTS.get(spec.type, "")


# * — numbers —


def format_number(value: Any) -> str:
    """12 -> '12', 12.5 -> '12,5' (Italian decimal comma), None -> ''."""
    if value is None or value == "":
        return ""
    if not is_number(value):
        return str(value)
    if value == int(value):
        return str(int(value))
    return f"{value}".replace(".", ",")


def parse_number_text(text: str, what: str = "") -> Optional[float]:
    """'' -> None, '12,5' -> 12.5; anything else raises an Italian ValueError."""
    clean = (text or "").strip().replace(" ", "")
    if not clean:
        return None
    try:
        number = float(clean.replace(",", "."))
    except ValueError:
        prefix = f"{what}: " if what else ""
        raise ValueError(f"{prefix}'{text.strip()}' non è un numero") from None
    return int(number) if number == int(number) else number


# * — states —


def empty_state(spec: BlockSpec) -> Any:
    kind = spec.type
    if kind in ("text", "longtext", "bookmark", "number", "date"):
        return ""
    if kind == "tags":
        return {"tags": [], "text": ""}
    if kind == "checklist":
        return []
    if kind == "progress":
        return {"status": None, "current": "", "total": format_number(spec.options.get("total"))}
    if kind == "link":
        return []
    return None  # rating, scale, choice


def value_to_state(spec: BlockSpec, value: Any) -> Any:
    """The state that shows an existing value; an empty state when there is none."""
    if value is None:
        return empty_state(spec)
    kind = spec.type
    if kind in ("text", "longtext", "bookmark", "date"):
        return str(value)
    if kind == "number":
        return format_number(value)
    if kind == "tags":
        return {"tags": list(value), "text": ""}
    if kind == "checklist":
        return [{"text": item.get("text", ""), "done": bool(item.get("done"))} for item in value]
    if kind == "progress":
        return {
            "status": value.get("status"),
            "current": format_number(value.get("current")),
            "total": format_number(value.get("total")),
        }
    if kind == "link":
        return list(value) if isinstance(value, list) else [value]
    return value  # rating, scale, choice


def initial_states(template: Template, values: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    values = values or {}
    return {spec.key: value_to_state(spec, values.get(spec.key)) for spec in template.blocks}


def state_to_raw(spec: BlockSpec, state: Any) -> Any:
    """The raw value for the core, or None when the field is empty. May raise ValueError."""
    kind = spec.type
    if state is None:
        return None
    if kind in ("text", "bookmark", "date"):
        text = str(state).strip()
        return text or None
    if kind == "longtext":
        text = str(state).replace("\r\n", "\n").strip()
        return text or None
    if kind == "number":
        return parse_number_text(str(state))
    if kind == "tags":
        tags = list(state.get("tags", [])) + split_tag_text(state.get("text", ""))
        return tags or None
    if kind == "checklist":
        items = [
            {"text": " ".join(str(item.get("text", "")).split()), "done": bool(item.get("done"))}
            for item in state
            if str(item.get("text", "")).strip()
        ]
        return items or None
    if kind == "progress":
        status = state.get("status")
        current = parse_number_text(state.get("current", ""), "a che punto sei")
        total = parse_number_text(state.get("total", ""), "totale")
        if status is None and current is None and (total is None or total == spec.options.get("total")):
            return None
        raw: Dict[str, Any] = {"status": status or ("ongoing" if current is not None else "not_started")}
        if current is not None:
            raw["current"] = current
        if total is not None:
            raw["total"] = total
        return raw
    if kind == "link":
        return list(state) or None
    return state  # rating, scale, choice


@dataclass
class FormResult:
    values: Dict[str, Any] = field(default_factory=dict)
    errors: Dict[str, str] = field(default_factory=dict)
    day: str = ""

    @property
    def ok(self) -> bool:
        return not self.errors


def collect_values(template: Template, states: Mapping[str, Any], day: str = "") -> FormResult:
    """Check every field with the core; errors go next to their field (by block key).

    `day` is the day of the entry ('' means today); its error is under DAY_KEY.
    A problem that belongs to no single field goes under FORM_KEY.
    """
    result = FormResult()
    for spec in template.blocks:
        try:
            raw = state_to_raw(spec, states.get(spec.key, empty_state(spec)))
            if raw is None or spec.block_type.is_empty(raw):
                if spec.required:
                    result.errors[spec.key] = REQUIRED_MESSAGE
                continue
            value = spec.block_type.normalize(raw, spec.options)
        except ValueError as error:
            result.errors[spec.key] = str(error)
            continue
        if spec.block_type.is_empty(value):
            if spec.required:
                result.errors[spec.key] = REQUIRED_MESSAGE
            continue
        result.values[spec.key] = value
    if day.strip():
        try:
            result.day = parse_day(day)
        except ValueError as error:
            result.errors[DAY_KEY] = str(error)
    if not result.errors:
        try:
            result.values = validate_values(template, result.values)
        except ValueError as error:
            result.errors[FORM_KEY] = str(error)
    return result


# * — tags —


def split_tag_text(text: str) -> List[str]:
    """'Roma, mare;  amici ' -> ['Roma', 'mare', 'amici'] (normalised later by the core)."""
    return [part.strip() for part in re.split(r"[,;]", text or "") if part.strip()]


def _normalise_tag(tag: str) -> str:
    return " ".join(tag.strip().lstrip("#").lower().split())


def absorb_tag_text(tags: Sequence[str], text: str, finish: bool = False) -> Tuple[List[str], str]:
    """Move the finished parts of the typed text into chips.

    'mare, mon' -> chip 'mare', still typing 'mon'. With `finish` (Enter, or
    leaving the field) the last part becomes a chip too.
    """
    parts = re.split(r"[,;]", text or "")
    remainder = "" if finish else parts.pop()
    result = list(tags)
    for part in parts:
        tag = _normalise_tag(part)
        if tag and tag not in result:
            result.append(tag)
    return result, remainder.lstrip()


def remove_tag(tags: Sequence[str], tag: str) -> List[str]:
    return [item for item in tags if item != tag]


def _plain(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", (text or "").lower())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def tag_suggestions(
    spec: BlockSpec, known: Iterable[str], current: Sequence[str], prefix: str = "", limit: int = 8
) -> List[str]:
    """The template's suggestions first, then tags already used; without the chosen ones."""
    wanted = _plain(_normalise_tag(split_tag_text(prefix)[-1] if split_tag_text(prefix) else ""))
    pool: List[str] = []
    for tag in list(spec.options.get("suggestions", [])) + list(known):
        tag = _normalise_tag(tag)
        if tag and tag not in pool and tag not in current:
            pool.append(tag)
    if wanted:
        pool = [tag for tag in pool if _plain(tag).startswith(wanted)] + [
            tag for tag in pool if wanted in _plain(tag) and not _plain(tag).startswith(wanted)
        ]
    return pool[:limit]


def known_tags(entries: Iterable[Entry], key: str) -> List[str]:
    """Tags used in a block across entries, most frequent first."""
    counts: Dict[str, int] = {}
    for entry in entries:
        for tag in entry.values.get(key, []) or []:
            counts[tag] = counts.get(tag, 0) + 1
    return [tag for tag, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0]))]


# * — rating, scale, choice —


def rating_max(spec: BlockSpec) -> int:
    return int(spec.options.get("max", 5))


def toggle_rating(current: Optional[int], clicked: int) -> Optional[int]:
    """Tap a star to set the vote; tap the same star again to clear it."""
    return None if current == clicked else clicked


def scale_bounds(spec: BlockSpec) -> Tuple[int, int]:
    return int(spec.options.get("min", 0)), int(spec.options.get("max", 10))


def scale_captions_from(options: Mapping[str, Any]) -> Tuple[str, str]:
    """('0 · a terra', '10 · al massimo'); just the numbers when there are no labels."""
    low, high = int(options.get("min", 0)), int(options.get("max", 10))
    low_label, high_label = options.get("low_label", ""), options.get("high_label", "")
    return (f"{low} · {low_label}" if low_label else str(low), f"{high} · {high_label}" if high_label else str(high))


def scale_captions(spec: BlockSpec) -> Tuple[str, str]:
    return scale_captions_from(spec.options)


def scale_value_text(spec: BlockSpec, state: Optional[int]) -> str:
    if state is None:
        return "non indicato"
    return f"{state}/{scale_bounds(spec)[1]}"


def choice_options(spec: BlockSpec) -> List[str]:
    return list(spec.options.get("choices", []))


def toggle_choice(current: Optional[str], clicked: str) -> Optional[str]:
    return None if current == clicked else clicked


# * — checklist —


def checklist_add(items: Sequence[Mapping[str, Any]], text: str) -> List[Dict[str, Any]]:
    """Add one item per non-empty line of `text`."""
    result = [dict(item) for item in items]
    for line in (text or "").splitlines():
        clean = " ".join(line.split())
        if clean:
            result.append({"text": clean, "done": False})
    return result


def checklist_progress(items: Sequence[Mapping[str, Any]]) -> Tuple[int, int]:
    """(done, total), counting only items with text."""
    real = [item for item in items if str(item.get("text", "")).strip()]
    return sum(1 for item in real if item.get("done")), len(real)


# * — progress —

PROGRESS_CHOICES: List[Tuple[str, str]] = list(PROGRESS_STATUSES.items())


def progress_fraction(value: Optional[Mapping[str, Any]]) -> Optional[float]:
    """0..1 for the progress bar; None when there is nothing to measure."""
    if not value:
        return None
    if value.get("status") == "completed":
        return 1.0
    current, total = value.get("current"), value.get("total")
    if is_number(current) and is_number(total) and total > 0:
        return max(0.0, min(1.0, current / total))
    return None


def progress_state_fraction(spec: BlockSpec, state: Mapping[str, Any]) -> Optional[float]:
    """Like `progress_fraction`, from what is being typed; None while it does not parse."""
    try:
        raw = state_to_raw(spec, state)
    except ValueError:
        return None
    if raw is None:
        return None
    if "total" not in raw and "total" in spec.options:
        raw["total"] = spec.options["total"]
    return progress_fraction(raw)


def progress_text(spec: BlockSpec, value: Mapping[str, Any]) -> str:
    return spec.block_type.to_text(value, spec.options)


# * — titles and links —


def entry_title(entry: Entry, template: Template, with_day: bool = False) -> str:
    """The value of the title block; else the template name (with the day, if asked)."""
    key = template.title_key
    if key and entry.values.get(key) not in (None, "", []):
        return str(entry.values[key])
    if with_day:
        return f"{template.name} del {_italian_day(entry.day)}"
    return template.name


def _italian_day(iso: str) -> str:
    months = ("gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic")
    try:
        year, month, day = (int(part) for part in iso.split("-"))
        return f"{day} {months[month - 1]} {year}"
    except (ValueError, IndexError):
        return iso


def link_candidates(
    spec: BlockSpec, entries: Iterable[Entry], templates: Mapping[str, Template], exclude_id: str = ""
) -> List[Tuple[str, str]]:
    """(id, 'Title · Template') of the entries this block may link, by title."""
    wanted = spec.options.get("template")
    result = []
    for entry in entries:
        if entry.id == exclude_id or (wanted and entry.template != wanted):
            continue
        template = templates.get(entry.template)
        if template is None:
            continue
        title = entry_title(entry, template, with_day=True)
        has_own_title = title != f"{template.name} del {_italian_day(entry.day)}"
        result.append((entry.id, f"{title} · {template.name}" if (has_own_title and not wanted) else title))
    return sorted(result, key=lambda item: _plain(item[1]))


def link_allows_many(spec: BlockSpec) -> bool:
    return bool(spec.options.get("multiple", True))


def add_link(current: Sequence[str], entry_id: str, many: bool) -> List[str]:
    if not many:
        return [entry_id]
    return list(current) if entry_id in current else list(current) + [entry_id]


def block_type_of(name: str) -> Optional[BlockType]:
    return BLOCK_TYPES.get(name)
