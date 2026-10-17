"""Export every entry to formats other programs read: Markdown and CSV, zipped.

- **Markdown** (Obsidian friendly): one folder per template, one `.md` per
  entry named `<day> <title>.md`, YAML front matter (template, day, id, areas
  when it has some, tags, created_at, updated_at) and one `##` section per
  filled block, written with the block's `to_text`. Links to other entries
  become `[[wikilinks]]`.
- **CSV** (for spreadsheets and pandas): one `<template>.csv` per template,
  UTF-8 with BOM (Excel reads the accents), columns id, day, area (the
  entry's main area), created_at, updated_at and then the block keys. Numbers
  and texts are written as they are, lists and objects as JSON, so nothing is
  lost.

`markdown_files` and `csv_files` only read the Store; `export_*` write the zip.
Exports are not encrypted: whoever opens the file can read the entries.
"""

import csv
import io
import json
import os
import re
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from zibaldone.core.areas import entry_areas, main_area
from zibaldone.core.templates import BlockSpec, Entry, Template
from zibaldone.storage.database import Store

UNSAFE_NAME_CHARS = re.compile(r'[\\/:*?"<>|#^\[\]\x00-\x1f]')  # Windows and Obsidian links
WINDOWS_RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL", *(f"COM{n}" for n in range(1, 10)), *(f"LPT{n}" for n in range(1, 10))}
MAX_NAME_LENGTH = 80
CSV_BASE_COLUMNS = ("id", "day", "area", "created_at", "updated_at")
CSV_ENCODING = "utf-8-sig"


@dataclass
class ExportResult:
    path: Path
    entries: int
    templates: int
    files: int


# * — names —


def safe_file_name(text: str, fallback: str) -> str:
    """A file or folder name valid on Windows, Android and in Obsidian links."""
    cleaned = " ".join(UNSAFE_NAME_CHARS.sub(" ", text).split()).strip(" .")
    cleaned = cleaned[:MAX_NAME_LENGTH].rstrip(" .") or fallback
    if cleaned.split(".")[0].upper() in WINDOWS_RESERVED_NAMES:
        cleaned = f"_{cleaned}"
    return cleaned


def _unique(name: str, suffix: str, used: Set[str]) -> str:
    """Case-insensitive uniqueness: Windows and macOS do not tell 'Dune' from 'dune'."""
    if name.lower() in used:
        name = f"{name} {suffix}"
    used.add(name.lower())
    return name


def obsidian_tag(tag: str) -> str:
    """Obsidian tags: no spaces or punctuation, and not only digits."""
    text = re.sub(r"[^\w\-/]", "", re.sub(r"\s+", "-", tag.strip())).strip("-/")
    return f"_{text}" if text.isdigit() else text


def _yaml_string(text: str) -> str:
    # A JSON string is a valid YAML double-quoted scalar.
    return json.dumps(text, ensure_ascii=False)


# * — Markdown —


def _in_order(entries: List[Entry]) -> List[Entry]:
    """Stable order, so the same data always gets the same file names."""
    return sorted(entries, key=lambda entry: (entry.day, entry.created_at, entry.id))


def _entry_base_name(entry: Entry, template: Template) -> str:
    key = template.title_key
    title = str(entry.values[key]) if key and entry.values.get(key) else template.name
    return safe_file_name(f"{entry.day} {title}", entry.day)


def _plan_paths(templates: Dict[str, Template], entries: List[Entry]) -> Dict[str, str]:
    """entry id -> 'Folder/Name' (without .md)."""
    folders: Dict[str, str] = {}
    used_folders: Set[str] = set()
    for slug, template in sorted(templates.items()):
        folders[slug] = _unique(safe_file_name(template.name, slug), f"({slug})", used_folders)
    used_names: Dict[str, Set[str]] = {slug: set() for slug in templates}
    paths = {}
    for entry in entries:
        name = _unique(_entry_base_name(entry, templates[entry.template]), entry.short_id, used_names[entry.template])
        paths[entry.id] = f"{folders[entry.template]}/{name}"
    return paths


def _tags(entry: Entry, template: Template) -> List[str]:
    tags: List[str] = []
    for block in template.blocks:
        if block.type == "tags":
            for tag in entry.values.get(block.key, []):
                converted = obsidian_tag(tag)
                if converted and converted not in tags:
                    tags.append(converted)
    return tags


def _plain(value: Any) -> str:
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def _block_text(block: BlockSpec, value: Any, links: Dict[str, Tuple[str, str]]) -> str:
    if block.type == "link":
        return ", ".join(f"[[{links[item][0]}|{links[item][1]}]]" if item in links else item[:8] for item in value)
    return block.block_type.to_text(value, block.options)


def entry_markdown(entry: Entry, template: Template, links: Dict[str, Tuple[str, str]]) -> str:
    """One entry as Markdown; `links` maps entry ids to (path, title) for wikilinks."""
    tags = ", ".join(_yaml_string(tag) for tag in _tags(entry, template))
    areas = entry_areas(entry, template)
    lines = [
        "---",
        f"template: {template.slug}",
        f"day: {entry.day}",
        f"id: {_yaml_string(entry.id)}",
        *([f"areas: [{', '.join(_yaml_string(area) for area in areas)}]"] if areas else []),
        f"tags: [{tags}]",
        f"created_at: {_yaml_string(entry.created_at)}",
        f"updated_at: {_yaml_string(entry.updated_at)}",
        "---",
        "",
        f"# {entry.title(template)}",
        "",
    ]
    for block in template.blocks:
        if block.key in entry.values:
            lines += [f"## {block.label}", "", _block_text(block, entry.values[block.key], links), ""]
    known = {block.key for block in template.blocks}
    for key in sorted(set(entry.values) - known):  # values of blocks removed from the template
        lines += [f"## {key}", "", _plain(entry.values[key]), ""]
    return "\n".join(lines)


def markdown_files(store: Store) -> Dict[str, str]:
    """Path inside the zip -> Markdown text, for every entry."""
    templates = {template.slug: template for template in store.list_templates()}
    entries = _in_order(store.list_entries())
    paths = _plan_paths(templates, entries)
    links = {entry.id: (paths[entry.id], entry.title(templates[entry.template])) for entry in entries}
    return {f"{paths[entry.id]}.md": entry_markdown(entry, templates[entry.template], links) for entry in entries}


# * — CSV —


def _csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (str, int, float)) and not isinstance(value, bool):
        return str(value)
    return json.dumps(value, ensure_ascii=False)


def template_csv(template: Template, entries: List[Entry]) -> str:
    keys = [block.key for block in template.blocks]
    keys += sorted({key for entry in entries for key in entry.values} - set(keys))
    columns = [*CSV_BASE_COLUMNS, *(f"blocco_{key}" if key in CSV_BASE_COLUMNS else key for key in keys)]
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(columns)
    for entry in entries:
        writer.writerow([entry.id, entry.day, main_area(entry, template), entry.created_at, entry.updated_at, *(_csv_value(entry.values.get(key)) for key in keys)])
    return buffer.getvalue()


def csv_files(store: Store) -> Dict[str, str]:
    """`<template>.csv` -> CSV text, also for templates without entries (header only)."""
    return {
        f"{template.slug}.csv": template_csv(template, _in_order(store.list_entries(template=template.slug)))
        for template in store.list_templates()
    }


# * — writing —


def _write_zip(files: Dict[str, bytes], target: Path) -> None:
    """Atomic: a half-written zip never takes the place of a good one."""
    if not target.parent.is_dir():
        raise ValueError(f"la cartella {target.parent} non esiste")
    handle, name = tempfile.mkstemp(prefix=".zbexport-", suffix=".zip", dir=target.parent)
    os.close(handle)
    try:
        with zipfile.ZipFile(name, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path, data in sorted(files.items()):
                archive.writestr(path, data)
        os.replace(name, target)
    finally:
        if os.path.exists(name):
            os.remove(name)


def export_markdown(store: Store, target: Path) -> ExportResult:
    files = markdown_files(store)
    _write_zip({path: text.encode("utf-8") for path, text in files.items()}, target)
    folders = {path.split("/", 1)[0] for path in files}
    return ExportResult(path=target, entries=len(files), templates=len(folders), files=len(files))


def export_csv(store: Store, target: Path) -> ExportResult:
    files = csv_files(store)
    _write_zip({path: text.encode(CSV_ENCODING) for path, text in files.items()}, target)
    return ExportResult(path=target, entries=store.count_entries(), templates=len(files), files=len(files))
