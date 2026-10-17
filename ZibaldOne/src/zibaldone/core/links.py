"""Collegamenti: links between entries, from link blocks and from [[Titolo]] in texts.

Pure functions; `storage/database.py` keeps them in the `links` table.
A `[[Titolo]]` resolves, ignoring case, to the entry with that title (or a
person with that nickname). When nothing matches it stays unresolved and
resolves by itself once an entry with that title exists.
"""

import re
import unicodedata
from dataclasses import dataclass
from typing import List, Optional, Tuple

from zibaldone.core.blocks import ENTRY_ID
from zibaldone.core.templates import Entry, Template

KIND_BLOCK = "block"
KIND_WIKI = "wiki"
WIKI_LINK = re.compile(r"\[\[([^\[\]\n|#]{1,200})(?:[#|][^\[\]\n]{0,200})?\]\]")
WIKI_LABEL = re.compile(r"\[\[([^\[\]\n|#]{1,200})(?:#[^\[\]\n|]{0,200})?(?:\|([^\[\]\n]{1,200}))?\]\]")
WIKI_TYPES = {"text", "longtext"}
ALIAS_KEYS = {"soprannomi", "soprannome", "alias", "aliases", "nickname", "nicknames"}
PERSON_SLUGS = {"persona", "persone", "person", "people", "contatto"}
PERSON_CATEGORIES = {"persone", "persona", "people"}


def name_key(text: str) -> str:
    """How titles are compared: case, width and extra spaces do not count."""
    return " ".join(unicodedata.normalize("NFKC", text).split()).casefold()


def wiki_targets(text: str) -> List[str]:
    """The titles written as [[Titolo]] (or [[Titolo|testo]], [[Titolo#parte]]), once each."""
    found: List[str] = []
    seen = set()
    for match in WIKI_LINK.finditer(text or ""):
        title = " ".join(match.group(1).split())
        key = name_key(title)
        if key and key not in seen:
            seen.add(key)
            found.append(title)
    return found


def plain_text(text: str) -> str:
    """Text with [[Titolo]] shown as Titolo and [[Titolo|testo]] as testo (for snippets)."""
    return WIKI_LABEL.sub(lambda match: match.group(2) or match.group(1), text or "")


def is_person_template(template: Template) -> bool:
    """A template that describes people ('persona' and similar), not encounters with them."""
    if template.slug.split("_")[0] in PERSON_SLUGS:
        return True
    has_links = any(block.type == "link" for block in template.blocks)
    return template.category in PERSON_CATEGORIES and not has_links


def alias_blocks(template: Template) -> List[str]:
    """Tags blocks holding nicknames, only for person templates."""
    if not is_person_template(template):
        return []
    return [
        block.key for block in template.blocks
        if block.type == "tags" and (block.key in ALIAS_KEYS or "soprannom" in block.label.lower() or "alias" in block.label.lower())
    ]


def entry_names(entry: Entry, template: Template) -> List[Tuple[str, bool]]:
    """(name key, is_alias) under which [[...]] finds this entry: its real title and nicknames."""
    names: List[Tuple[str, bool]] = []
    key = template.title_key
    if key and isinstance(entry.values.get(key), str):
        title = name_key(entry.values[key])
        if title:
            names.append((title, False))
    for block_key in alias_blocks(template):
        for alias in entry.values.get(block_key, []):
            alias_key = name_key(alias)
            if alias_key and all(alias_key != name for name, _ in names):
                names.append((alias_key, True))
    return names


@dataclass(frozen=True)
class OutgoingLink:
    """A link as written in an entry, before resolution."""

    kind: str
    block: str
    position: int
    target_ref: Optional[str] = None  # link blocks: the entry id stored in the block
    target_title: str = ""  # [[...]]: the title as written
    target_name: str = ""  # [[...]]: name_key(target_title)


def outgoing_links(entry: Entry, template: Template) -> List[OutgoingLink]:
    """Every link written in an entry: ids in link blocks and [[Titolo]] in texts."""
    links: List[OutgoingLink] = []
    position = 0
    for spec in template.blocks:
        value = entry.values.get(spec.key)
        if value is None:
            continue
        if spec.type == "link":
            for ref in value:
                if isinstance(ref, str) and ENTRY_ID.match(ref) and ref != entry.id:
                    links.append(OutgoingLink(KIND_BLOCK, spec.key, position, target_ref=ref))
                    position += 1
        elif spec.type in WIKI_TYPES and isinstance(value, str):
            for title in wiki_targets(value):
                links.append(OutgoingLink(KIND_WIKI, spec.key, position, target_title=title, target_name=name_key(title)))
                position += 1
    return links


@dataclass(frozen=True)
class LinkRecord:
    """A stored link: `target` is None while unresolved (or after the target was deleted)."""

    source: str
    target: Optional[str]
    kind: str
    block: str
    target_title: str = ""

    @property
    def resolved(self) -> bool:
        return self.target is not None


@dataclass
class LinkInfo:
    """A link with what is needed to show it: titles, days and templates of both ends."""

    kind: str
    block: str
    block_label: str
    source: str
    source_title: str
    source_day: str
    source_template: str
    target: Optional[str]
    target_title: str
    target_day: Optional[str] = None
    target_template: Optional[str] = None

    @property
    def resolved(self) -> bool:
        return self.target is not None

    @property
    def how(self) -> str:
        """Italian description of how the link was made."""
        if self.kind == KIND_WIKI:
            return f"citato in «{self.block_label}»"
        return f"nel blocco «{self.block_label}»"


@dataclass
class About:
    """Everything about one entry ("tutto su Marco")."""

    entry: Entry
    title: str
    outgoing: List[LinkInfo]
    backlinks: List[LinkInfo]
    mentions: list  # SearchHit list: texts naming the entry without [[...]]
