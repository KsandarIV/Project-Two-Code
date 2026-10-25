"""Templates (user recipes made of blocks) and entries (filled-in templates).

Both are plain dataclasses that turn into JSON and back without losses, so a
template can be saved, exported in a pack and shared (ADR-0005).
"""

import re
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from zibaldone.core.blocks import BlockType, get_block_type, parse_day
from zibaldone.core.brand import AREAS

SLUG = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")
MAX_BLOCKS = 60

TEMPLATE_FIELDS = {"slug", "name", "blocks", "description", "icon", "color", "category", "area", "areas", "title_block", "origin", "version"}
BLOCK_FIELDS = {"key", "type", "label", "required", "options", "help"}
ORIGIN_FIELDS = {"pack_id", "pack_version", "author"}


def slugify(text: str) -> str:
    """Turn 'Serie TV' into 'serie_tv' (accents removed, max 40 characters)."""
    replacements = str.maketrans("àáâäèéêëìíîïòóôöùúûüç", "aaaaeeeeiiiioooouuuuc")
    cleaned = re.sub(r"[^a-z0-9]+", "_", text.lower().translate(replacements)).strip("_")
    if not cleaned or not cleaned[0].isalpha():
        cleaned = f"m_{cleaned}" if cleaned else "modello"
    return cleaned[:40].rstrip("_")


def check_area(value: Any, what: str = "area") -> str:
    """'' (no area) or one of the 8 life areas (0.2.0)."""
    if value is None or value == "":
        return ""
    if not isinstance(value, str) or value.strip().lower() not in AREAS:
        raise ValueError(f"{what}: scegli una delle aree ({', '.join(AREAS)})")
    return value.strip().lower()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _check_keys(data: Dict[str, Any], allowed: set, what: str) -> None:
    if not isinstance(data, dict):
        raise ValueError(f"{what}: atteso un oggetto")
    unknown = set(data) - allowed
    if unknown:
        raise ValueError(f"{what}: campi non previsti {', '.join(sorted(unknown))}")


def _short_text(value: Any, what: str, limit: int, required: bool = False) -> str:
    if value is None and not required:
        return ""
    if not isinstance(value, str) or (required and not value.strip()):
        raise ValueError(f"{what}: serve un testo")
    text = " ".join(value.split())
    if len(text) > limit:
        raise ValueError(f"{what}: massimo {limit} caratteri")
    return text


@dataclass
class BlockSpec:
    """One block inside a template: which type, which label, which options."""

    key: str
    type: str
    label: str
    required: bool = False
    options: Dict[str, Any] = field(default_factory=dict)
    help: str = ""

    @property
    def block_type(self) -> BlockType:
        return get_block_type(self.type)

    def validate(self) -> None:
        if not SLUG.match(self.key):
            raise ValueError(f"chiave di blocco non valida: '{self.key}' (minuscole, numeri e _)")
        self.label = _short_text(self.label, f"etichetta del blocco '{self.key}'", 80, required=True)
        self.help = _short_text(self.help, f"aiuto del blocco '{self.key}'", 200)
        if not isinstance(self.required, bool):
            raise ValueError(f"'required' del blocco '{self.key}' deve essere true o false")
        if not isinstance(self.options, dict):
            raise ValueError(f"le opzioni del blocco '{self.key}' devono essere un oggetto")
        self.options = self.block_type.check_options(self.options)

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {"key": self.key, "type": self.type, "label": self.label}
        if self.required:
            data["required"] = True
        if self.options:
            data["options"] = dict(self.options)
        if self.help:
            data["help"] = self.help
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BlockSpec":
        _check_keys(data, BLOCK_FIELDS, "blocco")
        spec = cls(
            key=data.get("key", ""),
            type=data.get("type", ""),
            label=data.get("label", ""),
            required=data.get("required", False),
            options=dict(data.get("options", {})) if isinstance(data.get("options", {}), dict) else data.get("options"),
            help=data.get("help", ""),
        )
        spec.validate()
        return spec


@dataclass
class Template:
    """A recipe made of blocks, for example 'Libro' or 'Sera'."""

    slug: str
    name: str
    blocks: List[BlockSpec]
    description: str = ""
    icon: str = ""
    color: str = ""
    category: str = ""
    title_block: str = ""
    origin: Dict[str, str] = field(default_factory=dict)
    version: int = 1
    area: str = ""  # 0.2.0: the life area its entries belong to, unless an entry says otherwise
    areas: List[str] = field(default_factory=list)  # 0.3.2: more areas the template is in, besides `area`

    def validate(self) -> "Template":
        if not SLUG.match(self.slug):
            raise ValueError(f"nome tecnico del modello non valido: '{self.slug}' (minuscole, numeri e _)")
        self.name = _short_text(self.name, "nome del modello", 60, required=True)
        self.description = _short_text(self.description, "descrizione del modello", 300)
        self.icon = _short_text(self.icon, "icona", 60)
        self.category = _short_text(self.category, "categoria", 40).lower()
        self.area = check_area(self.area, "area del modello")
        if not isinstance(self.areas, list):
            raise ValueError("le altre aree del modello sono una lista")
        self.areas = [key for key in dict.fromkeys(check_area(value, "area del modello") for value in self.areas) if key and key != self.area]
        if self.color and not HEX_COLOR.match(self.color):
            raise ValueError("il colore deve essere nel formato #RRGGBB")
        if not isinstance(self.blocks, list) or not self.blocks:
            raise ValueError(f"il modello '{self.slug}' deve avere almeno un blocco")
        if len(self.blocks) > MAX_BLOCKS:
            raise ValueError(f"troppi blocchi (massimo {MAX_BLOCKS})")
        keys = [block.key for block in self.blocks]
        duplicates = sorted({key for key in keys if keys.count(key) > 1})
        if duplicates:
            raise ValueError(f"chiavi di blocco ripetute: {', '.join(duplicates)}")
        for block in self.blocks:
            block.validate()
        if self.title_block and self.title_block not in keys:
            raise ValueError(f"il blocco titolo '{self.title_block}' non esiste")
        if self.title_block and self.blocks[keys.index(self.title_block)].type == "secret":
            raise ValueError("un blocco segreto non può fare da titolo: il titolo si vede negli elenchi e nella ricerca")
        if isinstance(self.version, bool) or not isinstance(self.version, int) or self.version < 1:
            raise ValueError("la versione del modello è un intero da 1 in su")
        _check_keys(self.origin, ORIGIN_FIELDS, "provenienza")
        self.origin = {key: _short_text(value, f"provenienza.{key}", 120) for key, value in self.origin.items()}
        return self

    def block(self, key: str) -> BlockSpec:
        for block in self.blocks:
            if block.key == key:
                return block
        raise ValueError(f"il modello '{self.name}' non ha il blocco '{key}'")

    @property
    def title_key(self) -> Optional[str]:
        """The block used as the entry title: explicit, else the first short text."""
        if self.title_block:
            return self.title_block
        for block in self.blocks:
            if block.type == "text":
                return block.key
        return None

    def all_areas(self) -> List[str]:
        """Every area of the template, the main one first."""
        return ([self.area] if self.area else []) + self.areas

    def block_types(self) -> List[str]:
        return sorted({block.type for block in self.blocks})

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {"slug": self.slug, "name": self.name, "blocks": [block.to_dict() for block in self.blocks]}
        for key in ("description", "icon", "color", "category", "area", "title_block"):
            if getattr(self, key):
                data[key] = getattr(self, key)
        if self.areas:
            data["areas"] = list(self.areas)
        if self.origin:
            data["origin"] = dict(self.origin)
        if self.version != 1:
            data["version"] = self.version
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Template":
        _check_keys(data, TEMPLATE_FIELDS, "modello")
        blocks = data.get("blocks")
        if not isinstance(blocks, list):
            raise ValueError("il modello deve avere una lista 'blocks'")
        template = cls(
            slug=data.get("slug", ""),
            name=data.get("name", ""),
            blocks=[BlockSpec.from_dict(block) for block in blocks],
            description=data.get("description", ""),
            icon=data.get("icon", ""),
            color=data.get("color", ""),
            category=data.get("category", ""),
            area=data.get("area", ""),
            areas=list(data["areas"]) if isinstance(data.get("areas"), list) else data.get("areas", []),
            title_block=data.get("title_block", ""),
            origin=dict(data.get("origin", {})) if isinstance(data.get("origin", {}), dict) else data.get("origin"),
            version=data.get("version", 1),
        )
        return template.validate()


def validate_values(template: Template, values: Dict[str, Any], partial: bool = False) -> Dict[str, Any]:
    """Check and normalise the values of an entry. Empty values are dropped.

    With partial=True, required blocks may be missing (used while editing).
    """
    if not isinstance(values, dict):
        raise ValueError("i valori di una voce sono un oggetto")
    known = {block.key for block in template.blocks}
    unknown = set(values) - known
    if unknown:
        raise ValueError(f"il modello '{template.name}' non ha i blocchi: {', '.join(sorted(unknown))}")
    clean: Dict[str, Any] = {}
    for block in template.blocks:
        if block.key not in values:
            continue
        raw = values[block.key]
        if block.block_type.is_empty(raw):
            continue
        try:
            value = block.block_type.normalize(raw, block.options)
        except ValueError as error:
            raise ValueError(f"{block.label}: {error}") from None
        if not block.block_type.is_empty(value):
            clean[block.key] = value
    if not partial:
        missing = [block.label for block in template.blocks if block.required and block.key not in clean]
        if missing:
            raise ValueError(f"mancano i blocchi obbligatori: {', '.join(missing)}")
    return clean


@dataclass
class Entry:
    """A filled-in template. `day` is the day the entry is about.

    `area` (0.2.0) is the entry's own life area; empty means "the template's".
    """

    id: str
    template: str
    values: Dict[str, Any]
    day: str
    created_at: str
    updated_at: str
    area: str = ""

    @classmethod
    def new(cls, template: Template, values: Dict[str, Any], day: Optional[str] = None, area: Optional[str] = None) -> "Entry":
        timestamp = now_iso()
        return cls(
            id=uuid.uuid4().hex,
            template=template.slug,
            values=validate_values(template, values),
            day=parse_day(day) if day else date.today().isoformat(),
            created_at=timestamp,
            updated_at=timestamp,
            area=check_area(area),
        )

    @property
    def short_id(self) -> str:
        return self.id[:8]

    def title(self, template: Template) -> str:
        key = template.title_key
        if key and self.values.get(key):
            return str(self.values[key])
        return f"{template.name} del {self.day}"

    def text_of(self, template: Template) -> Dict[str, str]:
        """Plain text of every filled block, by label (for search, export, anonymizer)."""
        texts = {}
        for block in template.blocks:
            if block.key in self.values:
                texts[block.label] = block.block_type.to_text(self.values[block.key], block.options)
        return texts

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "id": self.id,
            "template": self.template,
            "day": self.day,
            "values": self.values,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if self.area:
            data["area"] = self.area
        return data
