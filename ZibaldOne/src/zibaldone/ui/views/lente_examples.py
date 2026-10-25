"""Lente · the example entries and views that show how saved views work, and the way to take them away again."""

from pathlib import Path
from typing import Any, Dict, List

from zibaldone.core import views as V
from zibaldone.core.packs import apply_install, find_builtin_pack, plan_install
from zibaldone.storage.database import StoreError
from zibaldone.ui import services

KEY = "lente_esempi"  # ids of what was added, in the ui settings, so that exactly that can be taken away
MUSEION = "museion"


def _progress(status: str, **extra: Any) -> Dict[str, Any]:
    return {"status": status, **extra}


EXAMPLES: List[Dict[str, Any]] = [
    {"template": "libro", "values": {"titolo": "Dune", "autore": "Frank Herbert", "stato": _progress("ongoing"), "generi": ["fantascienza"]}},
    {"template": "libro", "values": {"titolo": "Il nome della rosa", "autore": "Umberto Eco", "stato": _progress("completed"), "voto": 5, "generi": ["giallo storico"]}},
    {"template": "libro", "values": {"titolo": "Se questo è un uomo", "autore": "Primo Levi", "stato": _progress("wishlist"), "generi": ["testimonianza"]}},
    {"template": "film", "values": {"titolo": "Blade Runner", "regista": "Ridley Scott", "anno": 1982, "stato": _progress("completed"), "voto": 4, "generi": ["fantascienza"]}},
    {"template": "film", "values": {"titolo": "Il Gattopardo", "regista": "Luchino Visconti", "anno": 1963, "stato": _progress("wishlist"), "generi": ["drammatico"]}},
    {"template": "film", "values": {"titolo": "2001: Odissea nello spazio", "regista": "Stanley Kubrick", "anno": 1968, "stato": _progress("wishlist"), "generi": ["fantascienza"]}},
    {"template": "serie", "values": {"titolo": "Breaking Bad", "piattaforma": "Netflix", "stato": _progress("completed"), "voto": 5, "generi": ["drammatico"]}},
    {"template": "serie", "values": {"titolo": "Dark", "piattaforma": "Netflix", "stato": _progress("ongoing"), "generi": ["fantascienza"]}},
    {"template": "serie", "values": {"titolo": "Chernobyl", "piattaforma": "Sky", "stato": _progress("wishlist"), "generi": ["storico"]}},
]

# (name, template, field, value): the three views that make the examples useful
VIEWS = (
    ("Esempio · libri in corso", "libro", "stato", "In corso"),
    ("Esempio · film da vedere", "film", "stato", "Da fare"),
    ("Esempio · serie completate", "serie", "stato", "Completato"),
)


def _ensure(store: Any, slug: str, pack_name: str) -> None:
    if store.find_template(slug) is not None:
        return
    pack = find_builtin_pack(pack_name)
    if pack is None:
        raise ValueError(f"il pacchetto «{pack_name}» non è in questa versione")
    apply_install(plan_install(pack, store), store)


def added(folder: Path) -> List[str]:
    value = services.ui_settings(folder).get(KEY, [])
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def add(store: Any, folder: Path) -> int:
    """Install what the examples need (Lente, the collections), then add 9 entries and 3 views; returns how many entries."""
    if added(folder):
        return 0
    _ensure(store, V.TEMPLATE, V.PACK_NAME)
    _ensure(store, "libro", MUSEION)
    ids = [store.add_entry(example["template"], dict(example["values"])).id for example in EXAMPLES]
    for name, template, field, value in VIEWS:
        ids.append(V.save_view(store, name, template=template, field=field, value=value).id)
    services.save_ui_settings(folder, **{KEY: ids})
    return len(EXAMPLES)


def remove(store: Any, folder: Path) -> int:
    """Delete exactly what `add` made (what the person already removed is skipped); returns how many were removed."""
    count = 0
    for entry_id in added(folder):
        try:
            store.delete_entry(entry_id)
            count += 1
        except StoreError:  # already gone
            continue
    services.save_ui_settings(folder, **{KEY: []})
    return count
