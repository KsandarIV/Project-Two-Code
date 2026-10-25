"""Template packs: shareable files with templates only, never entries (ADR-0005).

A pack is plain JSON (`.zbpack.json`). Importing one is safe by design: it is
data, it is validated field by field, and nothing in it is ever executed.
"""

import json
import re
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from zibaldone.core.blocks import BLOCK_TYPES
from zibaldone.core.templates import Template, _check_keys, _short_text

PACK_FORMAT = 1
PACK_SUFFIX = ".zbpack.json"
MAX_PACK_BYTES = 1_000_000
MAX_TEMPLATES = 100
PACK_ID = re.compile(r"^[a-z0-9][a-z0-9_.-]{1,79}$")
PACK_VERSION = re.compile(r"^\d+\.\d+\.\d+$")
PACK_FIELDS = {"format", "id", "name", "version", "author", "license", "description", "required_blocks", "templates"}


@dataclass
class Pack:
    id: str
    name: str
    version: str
    templates: List[Template]
    author: str = ""
    license: str = ""
    description: str = ""

    def validate(self) -> "Pack":
        if not PACK_ID.match(self.id):
            raise ValueError(f"identificativo del pacchetto non valido: '{self.id}'")
        self.name = _short_text(self.name, "nome del pacchetto", 80, required=True)
        if not isinstance(self.version, str) or not PACK_VERSION.match(self.version):
            raise ValueError("la versione del pacchetto deve essere X.Y.Z")
        self.author = _short_text(self.author, "autore", 80)
        self.license = _short_text(self.license, "licenza", 40)
        self.description = _short_text(self.description, "descrizione del pacchetto", 500)
        if not self.templates:
            raise ValueError("il pacchetto non contiene modelli")
        if len(self.templates) > MAX_TEMPLATES:
            raise ValueError(f"troppi modelli nel pacchetto (massimo {MAX_TEMPLATES})")
        slugs = [template.slug for template in self.templates]
        if len(set(slugs)) != len(slugs):
            raise ValueError("il pacchetto contiene due modelli con lo stesso nome tecnico")
        return self

    @property
    def required_blocks(self) -> List[str]:
        return sorted({block_type for template in self.templates for block_type in template.block_types()})

    @property
    def short_name(self) -> str:
        return self.id.split(".")[-1]

    def to_dict(self) -> Dict[str, Any]:
        templates = []
        for template in self.templates:
            data = template.to_dict()
            data.pop("origin", None)
            templates.append(data)
        return {
            "format": PACK_FORMAT,
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "license": self.license,
            "description": self.description,
            "required_blocks": self.required_blocks,
            "templates": templates,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Pack":
        _check_keys(data, PACK_FIELDS, "pacchetto")
        pack_format = data.get("format")
        if not isinstance(pack_format, int) or isinstance(pack_format, bool) or pack_format < 1:
            raise ValueError("il file non è un pacchetto di ZibaldOne (manca 'format')")
        if pack_format > PACK_FORMAT:
            raise ValueError("il pacchetto usa un formato più recente: aggiorna ZibaldOne")
        required = data.get("required_blocks", [])
        if not isinstance(required, list):
            raise ValueError("'required_blocks' deve essere una lista")
        unknown = sorted(set(required) - set(BLOCK_TYPES))
        if unknown:
            raise ValueError(f"il pacchetto richiede blocchi che questa versione non conosce: {', '.join(unknown)}. Aggiorna ZibaldOne")
        raw_templates = data.get("templates")
        if not isinstance(raw_templates, list):
            raise ValueError("il pacchetto deve avere una lista 'templates'")
        if len(raw_templates) > MAX_TEMPLATES:
            raise ValueError(f"troppi modelli nel pacchetto (massimo {MAX_TEMPLATES})")
        templates = []
        for number, raw in enumerate(raw_templates, 1):
            if isinstance(raw, dict):
                raw = {key: value for key, value in raw.items() if key != "origin"}
            try:
                templates.append(Template.from_dict(raw))
            except ValueError as error:
                raise ValueError(f"modello {number} del pacchetto: {error}") from None
        pack = cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            version=data.get("version", ""),
            templates=templates,
            author=data.get("author", ""),
            license=data.get("license", ""),
            description=data.get("description", ""),
        ).validate()
        if sorted(required) != pack.required_blocks:
            raise ValueError("'required_blocks' non corrisponde ai blocchi usati dai modelli")
        return pack


def load_pack_bytes(data: bytes) -> Pack:
    if len(data) > MAX_PACK_BYTES:
        raise ValueError(f"pacchetto troppo grande (massimo {MAX_PACK_BYTES // 1000} KB)")
    try:
        parsed = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"il file non è un JSON valido: {error}") from None
    return Pack.from_dict(parsed)


def read_pack_file(path: Path) -> Pack:
    if not path.is_file():
        raise ValueError(f"file non trovato: {path}")
    if path.stat().st_size > MAX_PACK_BYTES:
        raise ValueError(f"pacchetto troppo grande (massimo {MAX_PACK_BYTES // 1000} KB)")
    return load_pack_bytes(path.read_bytes())


def write_pack_file(pack: Pack, path: Path) -> Path:
    if not path.name.endswith(PACK_SUFFIX):
        path = path.with_name(path.name.removesuffix(".json") + PACK_SUFFIX)
    path.write_text(pack.to_json(), encoding="utf-8")
    return path


# — built-in packs shipped with the app —


def builtin_packs() -> List[Pack]:
    folder = resources.files("zibaldone") / "packs"
    packs = [load_pack_bytes(item.read_bytes()) for item in folder.iterdir() if item.name.endswith(PACK_SUFFIX)]
    return sorted(packs, key=lambda pack: pack.id)


def find_builtin_pack(name: str) -> Optional[Pack]:
    for pack in builtin_packs():
        if name in (pack.id, pack.short_name):
            return pack
    return None


# — install plan —


@dataclass
class InstallStep:
    template: Template
    target_slug: str
    action: str  # "new", "update", "same", "copy"
    reason: str = ""


@dataclass
class InstallPlan:
    pack: Pack
    steps: List[InstallStep] = field(default_factory=list)

    def summary(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for step in self.steps:
            counts[step.action] = counts.get(step.action, 0) + 1
        return counts


def _same_content(left: Template, right: Template) -> bool:
    a, b = left.to_dict(), right.to_dict()
    a.pop("origin", None)
    b.pop("origin", None)
    return a == b


def plan_install(pack: Pack, store: Any) -> InstallPlan:
    """Decide what happens to each template, without changing anything.

    - new: the slug is free.
    - same: already installed from this pack with identical content (skipped).
    - update: installed from this pack and every existing entry still fits.
    - copy: the slug is taken by something else, or an update would break
      existing entries: install under a free slug instead.
    """
    from zibaldone.core.templates import validate_values

    plan = InstallPlan(pack)
    reserved: set = set()
    for template in pack.templates:
        existing = store.find_template(template.slug)
        if existing is None and template.slug not in reserved:
            plan.steps.append(InstallStep(template, template.slug, "new"))
            reserved.add(template.slug)
            continue
        if existing is not None and existing.origin.get("pack_id") == pack.id:
            if _same_content(existing, template):
                plan.steps.append(InstallStep(template, template.slug, "same", "già installato"))
                continue
            broken = 0
            for entry in store.list_entries(template=template.slug):
                try:
                    validate_values(template, entry.values)
                except ValueError:
                    broken += 1
            if not broken:
                plan.steps.append(InstallStep(template, template.slug, "update", "nuova versione dal pacchetto"))
                continue
            reason = f"{broken} voci non sarebbero compatibili con la nuova versione"
        else:
            reason = "nome tecnico già usato da un altro modello"
        target = store.free_slug(template.slug)
        while target in reserved:
            target = f"{target}_x"
        reserved.add(target)
        plan.steps.append(InstallStep(template, target, "copy", reason))
    return plan


def apply_install(plan: InstallPlan, store: Any) -> List[Template]:
    installed = []
    for step in plan.steps:
        if step.action == "same":
            continue
        data = step.template.to_dict()
        data["slug"] = step.target_slug
        data["origin"] = {"pack_id": plan.pack.id, "pack_version": plan.pack.version, "author": plan.pack.author}
        template = Template.from_dict(data)
        store.save_template(template, replace=step.action == "update")
        installed.append(template)
    return installed


def build_pack(
    templates: List[Template], pack_id: str, name: str, version: str = "1.0.0",
    author: str = "", license: str = "CC-BY-4.0", description: str = "",
) -> Pack:
    """Make a pack from the user's templates (structure only, no entries)."""
    copies = []
    for template in templates:
        data = template.to_dict()
        data.pop("origin", None)
        copies.append(Template.from_dict(data))
    return Pack(pack_id, name, version, copies, author, license, description).validate()


# — the packs a first start installs —

BASE_PACKS = ("diario", "aree", "persone", "collezioni", "io", "askesis", "theoria")  # not segreti or finanze: those stay on request


def install_base_packs(store: Any, names: Sequence[str] = BASE_PACKS) -> List[str]:
    """Install the packs in `names` (the base ones by default) and return the names of those it installed.

    A pack already there (its templates are in the store) is skipped, and so is one whose
    technical names are taken by something else: a first start never makes copies.
    """
    installed = []
    for name in names:
        pack = find_builtin_pack(name)
        if pack is None:
            continue
        plan = plan_install(pack, store)
        if all(step.action == "same" for step in plan.steps) or any(step.action == "copy" for step in plan.steps):
            continue
        apply_install(plan, store)
        installed.append(pack.short_name)
    return installed
