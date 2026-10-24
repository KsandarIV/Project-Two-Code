"""Theoria (0.2.8): saved searches, «tutti i libri in corso» one tap away.

A `vista` entry keeps the filters; running it is a search plus one optional
filter on a block, sorted by recency or by title. Secret blocks are never read:
a sealed amount or note cannot be a filter, the same as in the search.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Sequence

from zibaldone.core.areas import parse_area
from zibaldone.core.blocks import PROGRESS_STATUSES
from zibaldone.storage.database import MAX_SEARCH_LIMIT, StoreError

TEMPLATE = "vista"
PACK_NAME = "theoria"
RECENT, BY_TITLE = "Più recenti", "Titolo"
ORDERS = (RECENT, BY_TITLE)


class ViewError(ValueError):
    """A view action cannot run. Messages are for the user."""


@dataclass(frozen=True)
class View:
    id: str
    name: str
    template: str
    area: str
    text: str
    field: str
    value: str
    order: str


def _text(values: Dict[str, Any], key: str) -> str:
    value = values.get(key)
    return value.strip() if isinstance(value, str) else ""


def _template_check(store: Any) -> None:
    if store.find_template(TEMPLATE) is None:
        raise ViewError(f"manca il modello '{TEMPLATE}': installa la Scuola «Theoria · Viste» (`zbone pack install {PACK_NAME}`)")


def load_views(store: Any) -> List[View]:
    if store.find_template(TEMPLATE) is None:
        return []
    return [
        View(entry.id, _text(entry.values, "nome"), _text(entry.values, "modello"), _text(entry.values, "area"), _text(entry.values, "testo"), _text(entry.values, "campo"), _text(entry.values, "valore"), _text(entry.values, "ordine") or RECENT)
        for entry in store.list_entries(template=TEMPLATE, newest_first=False)
    ]


def find_view(views: Sequence[View], text: str) -> View:
    """By name or its first letters; an exact name wins; more than one match is an error that lists them."""
    wanted = " ".join(text.lower().split())
    exact = [view for view in views if view.name.lower() == wanted]
    found = exact or [view for view in views if wanted and view.name.lower().startswith(wanted)]
    if not found:
        raise ViewError(f"nessuna vista che inizia con «{text.strip()}»")
    if len(found) > 1:
        raise ViewError(f"«{text.strip()}» può essere più di una vista: " + ", ".join(view.name for view in found))
    return found[0]


def save_view(store: Any, name: str, template: str = "", area: str = "", text: str = "", field: str = "", value: str = "", order: str = RECENT) -> View:
    """Check the filters and keep them as a new view; an existing name is an error."""
    _template_check(store)
    name = " ".join(name.split())
    if not name:
        raise ViewError("la vista ha bisogno di un nome")
    if any(view.name.lower() == name.lower() for view in load_views(store)):
        raise ViewError(f"esiste già una vista chiamata «{name}»")
    template, text, field, value = template.strip(), text.strip(), field.strip(), value.strip()
    if template and store.find_template(template) is None:
        raise ViewError(f"nessun modello '{template}'")
    if area.strip():
        try:
            area = parse_area(area)
        except ValueError as error:
            raise ViewError(str(error)) from None
    if bool(field) != bool(value):
        raise ViewError("il filtro su un blocco vuole il campo e il valore, per esempio stato=In corso")
    if field and template and field not in {block.key for block in store.get_template(template).blocks}:
        raise ViewError(f"il modello '{template}' non ha un blocco '{field}'")
    if order not in ORDERS:
        raise ViewError(f"l'ordine è «{RECENT}» oppure «{BY_TITLE}»")
    try:
        entry = store.add_entry(TEMPLATE, {"nome": name, "modello": template, "area": area, "testo": text, "campo": field, "valore": value, "ordine": order})
    except (StoreError, ValueError) as error:
        raise ViewError(str(error)) from None
    return View(entry.id, name, template, area, text, field, value, order)


def delete_view(store: Any, view_id: str) -> bool:
    try:
        entry = store.get_entry(view_id)
    except StoreError:
        return False
    if entry.template != TEMPLATE:
        return False
    store.delete_entry(entry.id)
    return True


def _fold(value: Any) -> str:
    return " ".join(str(value).casefold().split())


def _spoken(value: Any) -> List[str]:
    """What a block value can be called: a progress status by key and by label, a list by its items."""
    if isinstance(value, dict):
        status = value.get("status")
        return [_fold(status), _fold(PROGRESS_STATUSES.get(status, status))] if status else []
    if isinstance(value, list):
        return [_fold(item.get("text", "") if isinstance(item, dict) else item) for item in value]
    return [] if value is None else [_fold(value)]


def _matches_field(entry: Any, templates: Dict[str, Any], field: str, value: str) -> bool:
    template = templates.get(entry.template)
    spec = next((block for block in template.blocks if block.key == field), None) if template else None
    if spec is None or spec.type == "secret":
        return False
    return _fold(value) in _spoken(entry.values.get(field))


def run_view(store: Any, view: View, limit: int = 200) -> List[Any]:
    """The entries of the view, sorted by the view's order. Entries with only sealed values match on their title alone."""
    if view.template and store.find_template(view.template) is None:
        raise ViewError(f"il modello '{view.template}' di questa vista non c'è più")
    hits = store.search(view.text, template=view.template or None, area=view.area or None, limit=MAX_SEARCH_LIMIT).hits
    if view.field:
        templates = {template.slug: template for template in store.list_templates()}
        hits = [hit for hit in hits if _matches_field(hit.entry, templates, view.field, view.value)]
    if view.order == BY_TITLE:
        hits = sorted(hits, key=lambda hit: hit.title.casefold())
    else:
        hits = sorted(hits, key=lambda hit: (hit.entry.day, hit.entry.created_at), reverse=True)
    return [hit.entry for hit in hits[: max(1, limit)]]
