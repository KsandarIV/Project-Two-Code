"""Sections, routes and layout choice. Pure: no Flet import.

Every screen has a route, so the app can start on any of them (handy for
tests and screenshots): `/oggi`, `/voci`, `/voci/<id>`, `/voci/<id>/modifica`,
`/scrivi/<modello>`, `/scrivi/<modello>/<area>`, `/collezioni`, `/modelli`,
`/modelli/nuovo`, `/modelli/<modello>`, `/scuole`, `/aree`, `/aree/<area>`,
`/organon`, `/organon/<parte>`.
"""

from dataclasses import dataclass
from typing import Optional, Tuple

from zibaldone.core.brand import AREAS, NOMENCLATURE
from zibaldone.ui.theme import WIDE_MIN_WIDTH

START_ROUTE_ENV = "ZIBALDONE_UI_START"


@dataclass(frozen=True)
class Section:
    """A destination of the main navigation: plain name plus philosophical name."""

    key: str
    route: str
    label: str
    nickname: str
    icon: str  # Flet icon name, resolved by the widgets
    selected_icon: str
    source: str  # where the philosophical name comes from


SECTIONS: Tuple[Section, ...] = (
    Section("oggi", "/oggi", "Oggi", NOMENCLATURE["today"].name, "TODAY_OUTLINED", "TODAY", NOMENCLATURE["today"].source),
    Section("voci", "/voci", "Voci", NOMENCLATURE["entry"].name, "EDIT_NOTE_OUTLINED", "EDIT_NOTE", NOMENCLATURE["entry"].source),
    Section(
        "collezioni", "/collezioni", "Collezioni", "Museion", "COLLECTIONS_BOOKMARK_OUTLINED", "COLLECTIONS_BOOKMARK",
        "il Museo di Alessandria, la casa delle Muse e dei libri",
    ),
    Section(
        "modelli", "/modelli", "Modelli", NOMENCLATURE["template"].name, "DASHBOARD_CUSTOMIZE_OUTLINED", "DASHBOARD_CUSTOMIZE",
        NOMENCLATURE["template"].source,
    ),
    Section(
        "organon", "/organon", "Impostazioni", NOMENCLATURE["settings"].name, "SETTINGS_OUTLINED", "SETTINGS",
        NOMENCLATURE["settings"].source,
    ),
)

SECTION_KEYS: Tuple[str, ...] = tuple(section.key for section in SECTIONS)


@dataclass(frozen=True)
class SettingsPart:
    key: str
    label: str
    nickname: str
    description: str
    icon: str


SETTINGS_PARTS: Tuple[SettingsPart, ...] = (
    SettingsPart("parresia", "Privacy e dati", NOMENCLATURE["privacy"].name, "dove sono i tuoi dati e cosa sa l'app", "SHIELD_OUTLINED"),
    SettingsPart("daimon", "Promemoria", NOMENCLATURE["reminders"].name, "quando e come ricordarti di scrivere", "NOTIFICATIONS_OUTLINED"),
    SettingsPart("mnemosyne", "Backup", NOMENCLATURE["history"].name, "le istantanee dei tuoi dati", "HISTORY"),
    SettingsPart("nuvole", "Account e cloud", NOMENCLATURE["cloud"].name, "l'account e dove vanno le copie", "CLOUD_OUTLINED"),
    SettingsPart("velo", "Anonimizzatore", NOMENCLATURE["anonymizer"].name, "togliere i dati personali da un testo, prima di un'IA", "VISIBILITY_OFF_OUTLINED"),
    SettingsPart("info", "Informazioni", "ZibaldOne", "il nome, le mascotte e i nomi filosofici", "INFO_OUTLINE"),
)
SETTINGS_KEYS: Tuple[str, ...] = tuple(part.key for part in SETTINGS_PARTS)


def section(key: str) -> Section:
    for item in SECTIONS:
        if item.key == key:
            return item
    raise KeyError(key)


def section_index(key: str) -> int:
    return SECTION_KEYS.index(key)


def settings_part(key: str) -> SettingsPart:
    for part in SETTINGS_PARTS:
        if part.key == key:
            return part
    raise KeyError(key)


def layout_for(width: Optional[float]) -> str:
    """'narrow' (phone: bottom bar) or 'wide' (desktop: rail on the left). Unknown width: wide."""
    if width is None or width <= 0:
        return "wide"
    return "narrow" if width < WIDE_MIN_WIDTH else "wide"


# * — routes —


@dataclass(frozen=True)
class Route:
    """A parsed route. `section` is the navigation item to highlight ('' keeps the current one)."""

    screen: str
    section: str
    arg: str = ""
    extra: str = ""  # a second argument: the area of a new entry (`/scrivi/<modello>/<area>`)

    @property
    def path(self) -> str:
        return route_path(self.screen, self.arg, self.extra)

    @property
    def is_top_level(self) -> bool:
        return self.screen in SECTION_KEYS


def route_path(screen: str, arg: str = "", extra: str = "") -> str:
    if screen in SECTION_KEYS:
        return f"/{screen}"
    paths = {
        "voce": f"/voci/{arg}",
        "modifica": f"/voci/{arg}/modifica",
        "scrivi": f"/scrivi/{arg}/{extra}" if extra else f"/scrivi/{arg}",
        "aree": "/aree",
        "area": f"/aree/{arg}",
        "modello": f"/modelli/{arg or 'nuovo'}",
        "scuole": "/scuole",
        "grafo": f"/grafo/{arg}" if arg else "/grafo",
        "theoria": "/theoria",
        "parte": f"/organon/{arg}",
        "consenso": "/benvenuto/consenso",
        "accesso": "/benvenuto/accesso",
        "copie": "/benvenuto/copie",
        "diario": "/benvenuto/diario",
    }
    return paths.get(screen, "/oggi")


HOME = Route("oggi", "oggi")


def parse_route(path: Optional[str]) -> Route:
    """Turn a path into a Route; anything unknown goes to Oggi."""
    clean = (path or "").split("?", 1)[0].split("#", 1)[0].strip()
    parts = [part for part in clean.split("/") if part]
    if not parts:
        return HOME
    head, rest = parts[0].lower(), parts[1:]
    if head in SECTION_KEYS and not rest:
        return Route(head, head)
    if head == "voci" and len(rest) == 1:
        return Route("voce", "voci", rest[0])
    if head == "voci" and len(rest) == 2 and rest[1] == "modifica":
        return Route("modifica", "voci", rest[0])
    if head == "scrivi" and len(rest) == 1:
        return Route("scrivi", "", rest[0])
    if head == "scrivi" and len(rest) == 2 and rest[1].lower() in AREAS:
        return Route("scrivi", "", rest[0], rest[1].lower())
    if head == "aree" and not rest:
        return Route("aree", "oggi")
    if head == "aree" and len(rest) == 1 and rest[0].lower() in AREAS:
        return Route("area", "oggi", rest[0].lower())
    if head == "modelli" and len(rest) == 1:
        return Route("modello", "modelli", "" if rest[0] == "nuovo" else rest[0])
    if head == "scuole" and not rest:
        return Route("scuole", "modelli")
    if head == "grafo" and len(rest) <= 1:
        return Route("grafo", "voci", rest[0] if rest else "")
    if head == "theoria" and not rest:
        return Route("theoria", "oggi")
    if head == "organon" and len(rest) == 1 and rest[0] in SETTINGS_KEYS:
        return Route("parte", "organon", rest[0])
    if head == "benvenuto" and len(rest) == 1 and rest[0] in ("consenso", "accesso", "copie", "diario"):
        return Route(rest[0], "")
    return HOME
