"""SQLite storage for templates and entries, with numbered migrations.

The database lives in the data folder as `zibaldone.db`. `PRAGMA user_version`
records which migrations ran; a newer app adds migrations, never edits old ones.

From 0.1.2 the store also keeps derived indexes (search text, tags, names and
links), always written in the same transaction as the entry they come from.
They can be rebuilt from the entries at any time (`rebuild_indexes`). The
FTS5 table is optional: SQLite builds without FTS5 use a LIKE search instead.

From 0.2.0 an entry can have its own life area (`entries.area`); the derived
table `entry_areas` lists every area of each entry (its own, its template's,
and those of an `aree` tags block), so lists and searches can filter by area.
"""

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple, Union

from zibaldone.core.areas import entry_areas
from zibaldone.core.templates import Entry, Template, check_area, now_iso, validate_values
from zibaldone.core.blocks import parse_day
from zibaldone.core.links import (
    KIND_BLOCK,
    KIND_WIKI,
    About,
    LinkInfo,
    LinkRecord,
    entry_names,
    is_person_template,
    name_key,
    outgoing_links,
    plain_text,
)
from zibaldone.core.search import (
    ENGINE_FTS,
    ENGINE_LIKE,
    FIELD_WEIGHTS,
    Document,
    Query,
    SearchHit,
    SearchResult,
    Term,
    display_text,
    entry_document,
    fallback_score,
    make_snippet,
    parse_query,
    words,
)

DATABASE_FILE = "zibaldone.db"
FTS_TABLE = "search_fts"
NO_FTS_ENV = "ZIBALDONE_NO_FTS"
MAX_SEARCH_LIMIT = 500

# * — migrations: append only —
MIGRATIONS: Sequence[str] = (
    # 1 — v0.0.3: templates and entries
    """
    CREATE TABLE templates (
        slug TEXT PRIMARY KEY,
        data TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE TABLE entries (
        id TEXT PRIMARY KEY,
        template TEXT NOT NULL REFERENCES templates(slug) ON DELETE RESTRICT,
        day TEXT NOT NULL,
        data TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE INDEX entries_by_template_day ON entries(template, day);
    CREATE INDEX entries_by_day ON entries(day);
    """,
    # 2 — 0.1.2: full-text search and links (Zetesis). Backfilled by `_reindex_all`;
    # the FTS5 table `search_fts` is created there too, only where SQLite has FTS5.
    """
    CREATE TABLE search_index (
        id INTEGER PRIMARY KEY,
        entry_id TEXT NOT NULL UNIQUE,
        template TEXT NOT NULL,
        day TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        title TEXT NOT NULL,
        name TEXT NOT NULL,
        body TEXT NOT NULL,
        tags TEXT NOT NULL,
        norm TEXT NOT NULL
    );
    CREATE INDEX search_index_by_day ON search_index(day);
    CREATE INDEX search_index_by_template ON search_index(template, day);
    CREATE TABLE entry_tags (
        entry_id TEXT NOT NULL,
        tag TEXT NOT NULL,
        PRIMARY KEY (entry_id, tag)
    );
    CREATE INDEX entry_tags_by_tag ON entry_tags(tag);
    CREATE TABLE entry_names (
        entry_id TEXT NOT NULL,
        name TEXT NOT NULL,
        alias INTEGER NOT NULL DEFAULT 0,
        person INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (entry_id, name)
    );
    CREATE INDEX entry_names_by_name ON entry_names(name);
    CREATE TABLE links (
        id INTEGER PRIMARY KEY,
        source TEXT NOT NULL,
        kind TEXT NOT NULL CHECK (kind IN ('block', 'wiki')),
        block TEXT NOT NULL,
        position INTEGER NOT NULL,
        target TEXT,
        target_ref TEXT,
        target_title TEXT NOT NULL DEFAULT '',
        target_name TEXT NOT NULL DEFAULT ''
    );
    CREATE INDEX links_by_source ON links(source, position);
    CREATE INDEX links_by_target ON links(target);
    CREATE INDEX links_by_ref ON links(target_ref);
    CREATE INDEX links_by_name ON links(target_name);
    CREATE TABLE index_state (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """,
    # 3 — 0.2.0: the 8 life areas (Eudaimonia). Backfilled by `_reindex_areas`.
    """
    ALTER TABLE entries ADD COLUMN area TEXT NOT NULL DEFAULT '';
    CREATE TABLE entry_areas (
        entry_id TEXT NOT NULL,
        area TEXT NOT NULL,
        PRIMARY KEY (entry_id, area)
    );
    CREATE INDEX entry_areas_by_area ON entry_areas(area);
    """,
)

# Python steps run right after a migration, inside its transaction (method names).
BACKFILLS: Dict[int, str] = {2: "_reindex_all", 3: "_reindex_areas"}
AREAS_SCHEMA = 3

# Order for resolving [[Titolo]]: not itself, people first, titles before nicknames, oldest first
# (rowid breaks ties within the same second).
_BEST_NAME = """
    COALESCE(
        (SELECT n.entry_id FROM entry_names n JOIN entries e ON e.id = n.entry_id
         WHERE n.name = links.target_name AND n.entry_id != links.source
         ORDER BY n.person DESC, n.alias, e.created_at, e.rowid LIMIT 1),
        (SELECT n.entry_id FROM entry_names n WHERE n.name = links.target_name AND n.entry_id = links.source)
    )
"""


class StoreError(Exception):
    """A storage operation was refused (missing item, conflict, …)."""


def database_path(folder: Path) -> Path:
    return folder / DATABASE_FILE


def fts5_available(connection: sqlite3.Connection) -> bool:
    """True when this SQLite build has FTS5 (not guaranteed on every Android build)."""
    try:
        connection.execute("CREATE VIRTUAL TABLE temp.zb_fts5_probe USING fts5(x)")
        connection.execute("DROP TABLE temp.zb_fts5_probe")
        return True
    except sqlite3.Error:
        return False


def _chunks(items: Sequence[Any], size: int = 500) -> Iterator[Sequence[Any]]:
    for start in range(0, len(items), size):
        yield items[start:start + size]


def _marks(count: int) -> str:
    return ", ".join("?" for _ in range(count))


class Store:
    """Access to templates and entries. Use as a context manager.

    `use_fts=False` forces the LIKE search even where FTS5 exists (also with
    the environment variable ZIBALDONE_NO_FTS=1).
    """

    def __init__(self, path: Path, use_fts: Optional[bool] = None) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.connection = sqlite3.connect(str(path))
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        if use_fts is None:
            use_fts = os.environ.get(NO_FTS_ENV, "") not in ("1", "true", "yes")
        self.fts = bool(use_fts) and fts5_available(self.connection)
        try:
            self.migrate()
        except Exception:
            self.connection.close()
            raise

    @classmethod
    def open(cls, folder: Path, use_fts: Optional[bool] = None) -> "Store":
        return cls(database_path(folder), use_fts=use_fts)

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def close(self) -> None:
        self.connection.close()

    # — schema —

    @property
    def schema_version(self) -> int:
        return self.connection.execute("PRAGMA user_version").fetchone()[0]

    def migrate(self) -> None:
        current = self.schema_version
        if current > len(MIGRATIONS):
            raise StoreError(
                f"il database è stato creato da una versione più recente di ZibaldOne (schema {current}): aggiorna l'app"
            )
        for number in range(current + 1, len(MIGRATIONS) + 1):
            with self.transaction() as cursor:
                cursor.executescript("BEGIN;" + MIGRATIONS[number - 1] + ";")
                backfill = BACKFILLS.get(number)
                if backfill:
                    getattr(self, backfill)()
                cursor.execute(f"PRAGMA user_version = {number}")
        self._prepare_indexes()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Cursor]:
        cursor = self.connection.cursor()
        try:
            yield cursor
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise
        finally:
            cursor.close()

    # — templates —

    def save_template(self, template: Template, replace: bool = False) -> Template:
        template.validate()
        data = json.dumps(template.to_dict(), ensure_ascii=False)
        previous = self.find_template(template.slug)
        exists = previous is not None
        if exists and not replace:
            raise StoreError(f"esiste già un modello '{template.slug}'")
        timestamp = now_iso()
        with self.transaction() as cursor:
            if exists:
                cursor.execute("UPDATE templates SET data = ?, updated_at = ? WHERE slug = ?", (data, timestamp, template.slug))
                if previous.to_dict() != template.to_dict():
                    self._reindex_template(template)
            else:
                cursor.execute(
                    "INSERT INTO templates (slug, data, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    (template.slug, data, timestamp, timestamp),
                )
        return template

    def find_template(self, slug: str) -> Optional[Template]:
        row = self.connection.execute("SELECT data FROM templates WHERE slug = ?", (slug,)).fetchone()
        return Template.from_dict(json.loads(row["data"])) if row else None

    def get_template(self, slug: str) -> Template:
        template = self.find_template(slug)
        if template is None:
            raise StoreError(f"non esiste un modello '{slug}'. Vedi `zbone template list`")
        return template

    def list_templates(self, category: Optional[str] = None) -> List[Template]:
        rows = self.connection.execute("SELECT data FROM templates ORDER BY slug").fetchall()
        templates = [Template.from_dict(json.loads(row["data"])) for row in rows]
        if category:
            templates = [template for template in templates if template.category == category]
        return templates

    def count_entries(self, template: Optional[str] = None) -> int:
        if template:
            return self.connection.execute("SELECT COUNT(*) FROM entries WHERE template = ?", (template,)).fetchone()[0]
        return self.connection.execute("SELECT COUNT(*) FROM entries").fetchone()[0]

    def delete_template(self, slug: str) -> None:
        self.get_template(slug)
        count = self.count_entries(slug)
        if count:
            raise StoreError(f"il modello '{slug}' ha {count} voci: cancellale prima di cancellare il modello")
        with self.transaction() as cursor:
            cursor.execute("DELETE FROM templates WHERE slug = ?", (slug,))

    def free_slug(self, slug: str) -> str:
        """Return `slug`, or `slug_2`, `slug_3` … if it is taken."""
        candidate, number = slug, 2
        while self.find_template(candidate) is not None:
            candidate = f"{slug[:36]}_{number}"
            number += 1
        return candidate

    # — entries —

    def _entry_from_row(self, row: sqlite3.Row) -> Entry:
        return Entry(
            id=row["id"],
            template=row["template"],
            values=json.loads(row["data"]),
            day=row["day"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            area=row["area"] if "area" in row.keys() else "",  # no column before migration 3
        )

    @property
    def has_areas(self) -> bool:
        return self.schema_version >= AREAS_SCHEMA

    def add_entry(self, template_slug: str, values: Dict[str, Any], day: Optional[str] = None, area: Optional[str] = None) -> Entry:
        """Add an entry. `area` is the entry's own life area (default: the template's)."""
        template = self.get_template(template_slug)
        entry = Entry.new(template, values, day, area=area)
        with self.transaction() as cursor:
            cursor.execute(
                "INSERT INTO entries (id, template, day, data, created_at, updated_at, area) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (entry.id, entry.template, entry.day, json.dumps(entry.values, ensure_ascii=False), entry.created_at, entry.updated_at, entry.area),
            )
            self.after_entry_saved(entry, template)
        return entry

    def get_entry(self, reference: str) -> Entry:
        """Find an entry by full id or by a unique prefix of at least 4 characters."""
        reference = reference.strip().lower()
        if len(reference) < 4:
            raise StoreError("scrivi almeno 4 caratteri dell'identificativo")
        rows = self.connection.execute("SELECT * FROM entries WHERE id LIKE ? LIMIT 2", (reference + "%",)).fetchall()
        if not rows:
            raise StoreError(f"nessuna voce con identificativo '{reference}'")
        if len(rows) > 1:
            raise StoreError(f"più voci iniziano con '{reference}': scrivi qualche carattere in più")
        return self._entry_from_row(rows[0])

    def list_entries(
        self,
        template: Optional[str] = None,
        day_from: Optional[str] = None,
        day_to: Optional[str] = None,
        limit: Optional[int] = None,
        newest_first: bool = True,
        area: Optional[str] = None,
    ) -> List[Entry]:
        """Entries by day. `area` keeps those in that life area (own, template's or listed)."""
        clauses, params = [], []
        if template:
            clauses.append("template = ?")
            params.append(template)
        if area:
            clauses.append("id IN (SELECT entry_id FROM entry_areas WHERE area = ?)")
            params.append(check_area(area))
        if day_from:
            clauses.append("day >= ?")
            params.append(parse_day(day_from))
        if day_to:
            clauses.append("day <= ?")
            params.append(parse_day(day_to))
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        order = "DESC" if newest_first else "ASC"
        sql = f"SELECT * FROM entries {where} ORDER BY day {order}, created_at {order}, rowid {order}"  # rowid: same second, insertion order
        if limit:
            sql += f" LIMIT {int(limit)}"
        return [self._entry_from_row(row) for row in self.connection.execute(sql, params).fetchall()]

    def update_entry(
        self, reference: str, values: Dict[str, Any], day: Optional[str] = None, merge: bool = True, area: Optional[str] = None
    ) -> Entry:
        """Change an entry. With merge=True, only the given blocks change; None clears a block.

        `area`: None leaves it as it is, '' goes back to the template's area.
        """
        entry = self.get_entry(reference)
        template = self.get_template(entry.template)
        new_values = dict(entry.values) if merge else {}
        for key, value in values.items():
            if value is None:
                new_values.pop(key, None)
            else:
                new_values[key] = value
        entry.values = validate_values(template, new_values)
        if day:
            entry.day = parse_day(day)
        if area is not None:
            entry.area = check_area(area)
        entry.updated_at = now_iso()
        with self.transaction() as cursor:
            cursor.execute(
                "UPDATE entries SET data = ?, day = ?, updated_at = ?, area = ? WHERE id = ?",
                (json.dumps(entry.values, ensure_ascii=False), entry.day, entry.updated_at, entry.area, entry.id),
            )
            self.after_entry_saved(entry, template)
        return entry

    def delete_entry(self, reference: str) -> Entry:
        entry = self.get_entry(reference)
        with self.transaction() as cursor:
            cursor.execute("DELETE FROM entries WHERE id = ?", (entry.id,))
            self.after_entry_deleted(entry)
        return entry

    # — hooks: keep the indexes in sync, inside the entry's transaction —

    def after_entry_saved(self, entry: Entry, template: Template) -> None:
        """Keep secondary indexes in sync. Extended from 0.1.2."""
        connection = self.connection
        old = connection.execute("SELECT title FROM search_index WHERE entry_id = ?", (entry.id,)).fetchone()
        old_names = {row[0] for row in connection.execute("SELECT name FROM entry_names WHERE entry_id = ?", (entry.id,))}
        links = outgoing_links(entry, template)
        refs = [link.target_ref for link in links if link.target_ref]
        titles = self._titles_of(refs)
        document = entry_document(entry, template, titles)
        self._write_document(entry, document)
        names = entry_names(entry, template)
        person = int(is_person_template(template))
        connection.execute("DELETE FROM entry_names WHERE entry_id = ?", (entry.id,))
        connection.executemany(
            "INSERT INTO entry_names (entry_id, name, alias, person) VALUES (?, ?, ?, ?)",
            [(entry.id, name, int(alias), person) for name, alias in names],
        )
        known_titles = {
            row[0]: row[1]
            for row in connection.execute(
                "SELECT target_ref, target_title FROM links WHERE source = ? AND kind = ? AND target_title != ''", (entry.id, KIND_BLOCK)
            )
        }
        connection.execute("DELETE FROM links WHERE source = ?", (entry.id,))
        connection.executemany(
            "INSERT INTO links (source, kind, block, position, target, target_ref, target_title, target_name) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    entry.id, link.kind, link.block, link.position,
                    link.target_ref if link.target_ref in titles else None, link.target_ref,
                    link.target_title or known_titles.get(link.target_ref, ""), link.target_name,
                )
                for link in links
            ],
        )
        affected = old_names | {name for name, _ in names} | {link.target_name for link in links if link.kind == KIND_WIKI}
        self._resolve_wiki(affected)
        self._write_areas(entry, template)
        if old is not None and old[0] != document.title:
            self._refresh_linkers(entry.id)

    def after_entry_deleted(self, entry: Entry) -> None:
        """Keep secondary indexes in sync. Extended from 0.1.2.

        Outgoing links go away; incoming ones become unresolved (a [[Titolo]]
        may resolve again to another entry with the same title).
        """
        connection = self.connection
        row = connection.execute("SELECT id, title FROM search_index WHERE entry_id = ?", (entry.id,)).fetchone()
        title = row["title"] if row else entry.id[:8]
        if row:
            self._delete_fts_row(row["id"])
            connection.execute("DELETE FROM search_index WHERE id = ?", (row["id"],))
        names = {name for (name,) in connection.execute("SELECT name FROM entry_names WHERE entry_id = ?", (entry.id,))}
        connection.execute("DELETE FROM entry_names WHERE entry_id = ?", (entry.id,))
        connection.execute("DELETE FROM entry_tags WHERE entry_id = ?", (entry.id,))
        if self.has_areas:
            connection.execute("DELETE FROM entry_areas WHERE entry_id = ?", (entry.id,))
        connection.execute("DELETE FROM links WHERE source = ?", (entry.id,))
        connection.execute(
            "UPDATE links SET target = NULL, target_title = CASE WHEN target_title = '' THEN ? ELSE target_title END "
            "WHERE kind = ? AND (target = ? OR target_ref = ?)",
            (title, KIND_BLOCK, entry.id, entry.id),
        )
        names |= {name for (name,) in connection.execute("SELECT DISTINCT target_name FROM links WHERE kind = ? AND target = ?", (KIND_WIKI, entry.id))}
        connection.execute("UPDATE links SET target = NULL WHERE kind = ? AND target = ?", (KIND_WIKI, entry.id))
        self._resolve_wiki(names)
        self._refresh_linkers(entry.id)

    # — 0.1.2: indexes (search text, tags, names, links) —

    def _template_map(self) -> Dict[str, Template]:
        templates = {}
        for row in self.connection.execute("SELECT slug, data FROM templates"):
            try:
                templates[row["slug"]] = Template.from_dict(json.loads(row["data"]))
            except (ValueError, TypeError):
                continue  # a broken template must not block the indexes of the others
        return templates

    def _titles_of(self, ids: Sequence[str]) -> Dict[str, str]:
        titles: Dict[str, str] = {}
        unique = list(dict.fromkeys(ids))
        for chunk in _chunks(unique):
            sql = f"SELECT e.id, s.title FROM entries e LEFT JOIN search_index s ON s.entry_id = e.id WHERE e.id IN ({_marks(len(chunk))})"
            for row in self.connection.execute(sql, list(chunk)):
                titles[row[0]] = row[1] or row[0][:8]
        return titles

    def _fts_table_exists(self) -> bool:
        return self.connection.execute("SELECT 1 FROM sqlite_master WHERE name = ?", (FTS_TABLE,)).fetchone() is not None

    def _ensure_fts(self) -> bool:
        """Create the FTS5 table if this SQLite has FTS5. Returns True when it was created now."""
        if not self.fts or self._fts_table_exists():
            return False
        for tokenizer in ("unicode61 remove_diacritics 2", "unicode61 remove_diacritics 1"):
            try:
                self.connection.execute(f"CREATE VIRTUAL TABLE {FTS_TABLE} USING fts5(title, body, tags, tokenize = '{tokenizer}')")
                return True
            except sqlite3.OperationalError:
                continue
        self.fts = False
        return False

    def _fill_fts(self) -> None:
        self.connection.execute(f"DELETE FROM {FTS_TABLE}")
        self.connection.execute(f"INSERT INTO {FTS_TABLE} (rowid, title, body, tags) SELECT id, name, body, tags FROM search_index")
        self.connection.execute("DELETE FROM index_state WHERE key = 'fts_stale'")

    def _mark_fts_stale(self) -> None:
        # Written without FTS5 (for example on a phone): the FTS table, if any, is rebuilt where FTS5 exists.
        self.connection.execute("INSERT OR REPLACE INTO index_state (key, value) VALUES ('fts_stale', '1')")

    def _delete_fts_row(self, rowid: int) -> None:
        if self.fts:
            self.connection.execute(f"DELETE FROM {FTS_TABLE} WHERE rowid = ?", (rowid,))
        else:
            self._mark_fts_stale()

    def _write_document(self, entry: Entry, document: Document) -> None:
        connection = self.connection
        values = (entry.template, entry.day, entry.updated_at, document.title, document.name, document.body, document.tags_text, document.norm())
        row = connection.execute("SELECT id FROM search_index WHERE entry_id = ?", (entry.id,)).fetchone()
        if row:
            rowid = row[0]
            connection.execute(
                "UPDATE search_index SET template = ?, day = ?, updated_at = ?, title = ?, name = ?, body = ?, tags = ?, norm = ? WHERE id = ?",
                (*values, rowid),
            )
        else:
            rowid = connection.execute(
                "INSERT INTO search_index (entry_id, template, day, updated_at, title, name, body, tags, norm) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (entry.id, *values),
            ).lastrowid
        self._delete_fts_row(rowid)
        if self.fts:
            connection.execute(
                f"INSERT INTO {FTS_TABLE} (rowid, title, body, tags) VALUES (?, ?, ?, ?)",
                (rowid, document.name, document.body, document.tags_text),
            )
        connection.execute("DELETE FROM entry_tags WHERE entry_id = ?", (entry.id,))
        connection.executemany("INSERT INTO entry_tags (entry_id, tag) VALUES (?, ?)", [(entry.id, tag) for tag in document.tags])

    def _resolve_wiki(self, names: Iterable[str]) -> None:
        wanted = sorted({name for name in names if name})
        for chunk in _chunks(wanted):
            self.connection.execute(
                f"UPDATE links SET target = ({_BEST_NAME}) WHERE kind = ? AND target_name IN ({_marks(len(chunk))})",
                (KIND_WIKI, *chunk),
            )

    def _refresh_linkers(self, entry_id: str) -> None:
        """Entries linking to `entry_id` through a link block carry its title in their text."""
        sources = [row[0] for row in self.connection.execute("SELECT DISTINCT source FROM links WHERE kind = ? AND target_ref = ?", (KIND_BLOCK, entry_id))]
        if not sources:
            return
        templates = self._template_map()
        for chunk in _chunks(sources):
            rows = self.connection.execute(f"SELECT * FROM entries WHERE id IN ({_marks(len(chunk))})", list(chunk)).fetchall()
            for row in rows:
                entry = self._entry_from_row(row)
                template = templates.get(entry.template)
                if template is None:
                    continue
                refs = [link.target_ref for link in outgoing_links(entry, template) if link.target_ref]
                self._write_document(entry, entry_document(entry, template, self._titles_of(refs)))

    # — 0.2.0: areas —

    def _write_areas(self, entry: Entry, template: Optional[Template]) -> None:
        if not self.has_areas:
            return
        self.connection.execute("DELETE FROM entry_areas WHERE entry_id = ?", (entry.id,))
        self.connection.executemany(
            "INSERT INTO entry_areas (entry_id, area) VALUES (?, ?)", [(entry.id, area) for area in entry_areas(entry, template)]
        )

    def _reindex_areas(self) -> None:
        """Rebuild `entry_areas` from the entries (migration 3 backfill; also part of `_reindex_all`)."""
        if not self.has_areas and not self._table_exists("entry_areas"):
            return
        templates = self._template_map()
        self.connection.execute("DELETE FROM entry_areas")
        rows = []
        for row in self.connection.execute("SELECT * FROM entries"):
            entry = self._entry_from_row(row)
            rows += [(entry.id, area) for area in entry_areas(entry, templates.get(entry.template))]
        self.connection.executemany("INSERT INTO entry_areas (entry_id, area) VALUES (?, ?)", rows)

    def _table_exists(self, name: str) -> bool:
        return self.connection.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)).fetchone() is not None

    def areas_of(self, reference: str) -> List[str]:
        """The life areas of an entry, from the index."""
        entry = self.get_entry(reference)
        template = self.find_template(entry.template)
        return entry_areas(entry, template)

    def area_counts(self) -> Dict[str, int]:
        """Number of entries in each area that has any."""
        if not self.has_areas:
            return {}
        return {row[0]: row[1] for row in self.connection.execute("SELECT area, COUNT(*) FROM entry_areas GROUP BY area")}

    def _reindex_template(self, template: Template) -> None:
        rows = self.connection.execute("SELECT * FROM entries WHERE template = ?", (template.slug,)).fetchall()
        for row in rows:
            self.after_entry_saved(self._entry_from_row(row), template)

    def _reindex_all(self) -> None:
        """Rebuild every index from the entries (migration 2 backfill and repairs)."""
        connection = self.connection
        templates = self._template_map()
        entries = [self._entry_from_row(row) for row in connection.execute("SELECT * FROM entries ORDER BY created_at, rowid")]
        titles = {entry.id: entry.title(templates[entry.template]) if entry.template in templates else entry.id[:8] for entry in entries}
        known_titles = {
            (row[0], row[1]): row[2]
            for row in connection.execute("SELECT source, target_ref, target_title FROM links WHERE kind = ? AND target_title != ''", (KIND_BLOCK,))
        }
        for table in ("search_index", "entry_tags", "entry_names", "links"):
            connection.execute(f"DELETE FROM {table}")
        index_rows, tag_rows, name_rows, link_rows = [], [], [], []
        for entry in entries:
            template = templates.get(entry.template)
            if template is None:
                document = Document(titles[entry.id], "", "", [])
                index_rows.append((entry.id, entry.template, entry.day, entry.updated_at, document.title, "", "", "", document.norm()))
                continue
            document = entry_document(entry, template, titles)
            index_rows.append((entry.id, entry.template, entry.day, entry.updated_at, document.title, document.name, document.body, document.tags_text, document.norm()))
            tag_rows += [(entry.id, tag) for tag in document.tags]
            person = int(is_person_template(template))
            name_rows += [(entry.id, name, int(alias), person) for name, alias in entry_names(entry, template)]
            for link in outgoing_links(entry, template):
                target = link.target_ref if link.target_ref in titles else None
                title = link.target_title or known_titles.get((entry.id, link.target_ref), "")
                link_rows.append((entry.id, link.kind, link.block, link.position, target, link.target_ref, title, link.target_name))
        connection.executemany(
            "INSERT INTO search_index (entry_id, template, day, updated_at, title, name, body, tags, norm) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", index_rows
        )
        connection.executemany("INSERT INTO entry_tags (entry_id, tag) VALUES (?, ?)", tag_rows)
        connection.executemany("INSERT OR IGNORE INTO entry_names (entry_id, name, alias, person) VALUES (?, ?, ?, ?)", name_rows)
        connection.executemany(
            "INSERT INTO links (source, kind, block, position, target, target_ref, target_title, target_name) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", link_rows
        )
        connection.execute(f"UPDATE links SET target = ({_BEST_NAME}) WHERE kind = ?", (KIND_WIKI,))
        self._reindex_areas()
        self._ensure_fts()
        if self.fts:
            self._fill_fts()
        else:
            self._mark_fts_stale()

    def _stale_index(self) -> bool:
        """Entries changed outside the Store (or an index row without its entry)."""
        missing = self.connection.execute(
            "SELECT 1 FROM entries e LEFT JOIN search_index s ON s.entry_id = e.id "
            "WHERE s.entry_id IS NULL OR s.updated_at != e.updated_at OR s.day != e.day OR s.template != e.template LIMIT 1"
        ).fetchone()
        orphan = self.connection.execute(
            "SELECT 1 FROM search_index s LEFT JOIN entries e ON e.id = s.entry_id WHERE e.id IS NULL LIMIT 1"
        ).fetchone()
        return bool(missing or orphan)

    def _prepare_indexes(self) -> None:
        """At open: create or refresh the FTS5 table where possible, repair stale indexes."""
        if self.schema_version < 2:
            return
        stale_fts = self.connection.execute("SELECT value FROM index_state WHERE key = 'fts_stale'").fetchone()
        needs_fts = self.fts and (not self._fts_table_exists() or stale_fts is not None)
        stale = self._stale_index()
        if not needs_fts and not stale:
            return
        with self.transaction():
            if stale:
                self._reindex_all()
            else:
                self._ensure_fts()
                if self.fts:
                    self._fill_fts()

    def rebuild_indexes(self) -> None:
        """Rebuild search, tags, names, links and areas from the entries."""
        with self.transaction():
            self._reindex_all()

    @property
    def search_engine(self) -> str:
        """'fts5' (SQLite full-text search) or 'like' (fallback without FTS5)."""
        return ENGINE_FTS if self.fts else ENGINE_LIKE

    # — 0.1.2: search (Zetesis) —

    def search(
        self,
        query: Union[str, Query],
        template: Optional[str] = None,
        tags: Sequence[str] = (),
        since: Optional[str] = None,
        until: Optional[str] = None,
        limit: int = 50,
        engine: Optional[str] = None,
        area: Optional[str] = None,
    ) -> SearchResult:
        """Search entries. Words are ANDed; "frase", parol* and -parola work; the filters narrow down.

        An empty query lists the entries matching the filters, newest first.
        `engine` forces 'like' (or 'fts5' where available); by default the best one runs.
        """
        parsed = query if isinstance(query, Query) else parse_query(query)
        engine = engine or self.search_engine
        if engine not in (ENGINE_FTS, ENGINE_LIKE):
            raise StoreError(f"motore di ricerca sconosciuto: {engine}")
        if engine == ENGINE_FTS and not self.fts:
            raise StoreError("la ricerca a testo pieno (FTS5) non è disponibile su questo dispositivo")
        limit = max(1, min(int(limit), MAX_SEARCH_LIMIT))
        if parsed.unusable:
            return SearchResult(parsed, [], engine, 0)
        clauses, params = [], []
        if template:
            clauses.append("s.template = ?")
            params.append(template)
        if since:
            clauses.append("s.day >= ?")
            params.append(parse_day(since))
        if until:
            clauses.append("s.day <= ?")
            params.append(parse_day(until))
        if area:
            clauses.append("s.entry_id IN (SELECT entry_id FROM entry_areas WHERE area = ?)")
            params.append(check_area(area))
        for tag in tags:
            tag = " ".join(tag.strip().lstrip("#").lower().split())
            if tag:
                clauses.append("s.entry_id IN (SELECT entry_id FROM entry_tags WHERE tag = ?)")
                params.append(tag)
        if engine == ENGINE_FTS:
            rows, total = self._search_fts(parsed, clauses, params, limit)
        else:
            rows, total = self._search_like(parsed, clauses, params, limit)
        return SearchResult(parsed, self._hits(rows, parsed), engine, total)

    def _search_fts(self, query: Query, clauses: List[str], params: List[Any], limit: int) -> Tuple[List[Tuple[sqlite3.Row, float]], int]:
        clauses, params = list(clauses), list(params)
        if query.exclude:
            clauses.append(f"s.id NOT IN (SELECT rowid FROM {FTS_TABLE} WHERE {FTS_TABLE} MATCH ?)")
            params.append(query.fts_exclusion())
        if not query.include:
            return self._list_filtered(clauses, params, limit)
        where = " AND ".join([f"{FTS_TABLE} MATCH ?"] + clauses)
        params = [query.fts_match()] + params
        source = f"FROM {FTS_TABLE} JOIN search_index s ON s.id = {FTS_TABLE}.rowid WHERE {where}"
        weights = ", ".join(str(weight) for weight in FIELD_WEIGHTS)
        rows = self.connection.execute(
            f"SELECT s.*, -bm25({FTS_TABLE}, {weights}) AS rank {source} ORDER BY rank DESC, s.day DESC, s.entry_id LIMIT ?",
            params + [limit],
        ).fetchall()
        total = self.connection.execute(f"SELECT COUNT(*) {source}", params).fetchone()[0]
        return [(row, float(row["rank"])) for row in rows], total

    def _search_like(self, query: Query, clauses: List[str], params: List[Any], limit: int) -> Tuple[List[Tuple[sqlite3.Row, float]], int]:
        clauses, params = list(clauses), list(params)
        for term in query.exclude:
            clauses.append("s.norm NOT LIKE ? ESCAPE '\\'")
            params.append(term.like())
        if not query.include:
            return self._list_filtered(clauses, params, limit)
        for term in query.include:
            clauses.append("s.norm LIKE ? ESCAPE '\\'")
            params.append(term.like())
        rows = self.connection.execute(f"SELECT s.id, s.day, s.entry_id, s.norm FROM search_index s WHERE {' AND '.join(clauses)}", params).fetchall()
        scored = sorted(
            ((fallback_score(row["norm"], query), row["day"], row["entry_id"], row["id"]) for row in rows),
            key=lambda item: (-item[0], _descending(item[1]), item[2]),
        )[:limit]
        full = {}
        for chunk in _chunks([item[3] for item in scored]):
            for row in self.connection.execute(f"SELECT * FROM search_index WHERE id IN ({_marks(len(chunk))})", list(chunk)):
                full[row["id"]] = row
        return [(full[item[3]], item[0]) for item in scored], len(rows)

    def _list_filtered(self, clauses: List[str], params: List[Any], limit: int) -> Tuple[List[Tuple[sqlite3.Row, float]], int]:
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.connection.execute(f"SELECT s.* FROM search_index s {where} ORDER BY s.day DESC, s.id DESC LIMIT ?", params + [limit]).fetchall()
        total = self.connection.execute(f"SELECT COUNT(*) FROM search_index s {where}", params).fetchone()[0]
        return [(row, 0.0) for row in rows], total

    def _hits(self, rows: List[Tuple[sqlite3.Row, float]], query: Query) -> List[SearchHit]:
        ids = [row["entry_id"] for row, _ in rows]
        entries: Dict[str, Entry] = {}
        for chunk in _chunks(ids):
            for row in self.connection.execute(f"SELECT * FROM entries WHERE id IN ({_marks(len(chunk))})", list(chunk)):
                entries[row["id"]] = self._entry_from_row(row)
        hits = []
        for row, rank in rows:
            entry = entries.get(row["entry_id"])
            if entry is None:
                continue
            snippet = make_snippet(display_text(plain_text(row["body"])), query)
            if not snippet.highlights and query.include:
                from_tags = make_snippet(row["tags"], query)
                if from_tags.highlights:
                    snippet = from_tags
            title = make_snippet(row["title"], query, whole=True)
            hits.append(SearchHit(entry=entry, title=row["title"], title_highlights=title.highlights, snippet=snippet, rank=rank))
        return hits

    # — 0.1.2: links and backlinks —

    def _link_infos(self, where: str, params: Sequence[Any], order: str) -> List[LinkInfo]:
        sql = f"""
            SELECT l.kind, l.block, l.source, l.target, l.target_ref, l.target_title AS written_title,
                   src.title AS source_title, src.day AS source_day, src.template AS source_template,
                   dst.title AS target_title, dst.day AS target_day, dst.template AS target_template
            FROM links l
            JOIN search_index src ON src.entry_id = l.source
            LEFT JOIN search_index dst ON dst.entry_id = l.target
            WHERE {where} ORDER BY {order}
        """
        labels = {
            (template.slug, block.key): block.label for template in self._template_map().values() for block in template.blocks
        }
        infos = []
        for row in self.connection.execute(sql, list(params)):
            resolved = row["target"] is not None and row["target_title"] is not None
            if resolved:
                target_title = row["target_title"]
            else:
                target_title = row["written_title"] or (f"voce cancellata ({row['target_ref'][:8]})" if row["target_ref"] else "")
            infos.append(
                LinkInfo(
                    kind=row["kind"],
                    block=row["block"],
                    block_label=labels.get((row["source_template"], row["block"]), row["block"]),
                    source=row["source"],
                    source_title=row["source_title"],
                    source_day=row["source_day"],
                    source_template=row["source_template"],
                    target=row["target"] if resolved else None,
                    target_title=target_title,
                    target_day=row["target_day"] if resolved else None,
                    target_template=row["target_template"] if resolved else None,
                )
            )
        return infos

    def outgoing(self, reference: str) -> List[LinkInfo]:
        """Links written in an entry, in block order; unresolved ones have target None."""
        entry = self.get_entry(reference)
        return self._link_infos("l.source = ? AND (l.target IS NULL OR l.target != l.source)", (entry.id,), "l.position")

    def backlinks(self, reference: str) -> List[LinkInfo]:
        """Entries pointing to this one: link blocks and [[Titolo]] in their texts, newest first."""
        entry = self.get_entry(reference)
        return self._link_infos("l.target = ? AND l.source != l.target", (entry.id,), "src.day DESC, src.entry_id, l.position")

    def unlinked_mentions(self, reference: str, limit: int = 20) -> List[SearchHit]:
        """Texts that name the entry (title or nickname) without linking it."""
        entry = self.get_entry(reference)
        names = [row[0] for row in self.connection.execute("SELECT name FROM entry_names WHERE entry_id = ? ORDER BY alias, name", (entry.id,))]
        skip = {entry.id} | {row[0] for row in self.connection.execute("SELECT source FROM links WHERE target = ?", (entry.id,))}
        found: Dict[str, SearchHit] = {}
        for name in names:
            parts = tuple(words(name))
            if not parts:
                continue
            result = self.search(Query(text=name, terms=(Term(parts),)), limit=limit + len(skip))
            for hit in result.hits:
                if hit.entry.id not in skip and hit.entry.id not in found:
                    found[hit.entry.id] = hit
        hits = sorted(found.values(), key=lambda hit: (_descending(hit.entry.day), hit.entry.id))
        return hits[:limit]

    def about(self, reference: str, mentions: int = 20) -> About:
        """Everything about an entry: its links, who links to it, who names it ("tutto su Marco")."""
        entry = self.get_entry(reference)
        title = self._titles_of([entry.id]).get(entry.id, entry.id[:8])
        return About(
            entry=entry,
            title=title,
            outgoing=self.outgoing(entry.id),
            backlinks=self.backlinks(entry.id),
            mentions=self.unlinked_mentions(entry.id, mentions) if mentions else [],
        )

    def resolve_title(self, title: str) -> Optional[Entry]:
        """The entry that [[title]] points to, if any (people first)."""
        key = name_key(title)
        if not key:
            return None
        row = self.connection.execute(
            "SELECT e.* FROM entry_names n JOIN entries e ON e.id = n.entry_id WHERE n.name = ? "
            "ORDER BY n.person DESC, n.alias, e.created_at, e.rowid LIMIT 1",
            (key,),
        ).fetchone()
        return self._entry_from_row(row) if row else None

    def all_links(self) -> List[LinkRecord]:
        """Every stored link (for the graph and the statistics); self links are left out."""
        rows = self.connection.execute(
            "SELECT source, target, kind, block, target_title FROM links WHERE target IS NULL OR target != source ORDER BY source, position"
        )
        return [LinkRecord(row[0], row[1], row[2], row[3], row[4]) for row in rows]

    def entry_titles(self) -> Dict[str, str]:
        """Display title of every entry, by id."""
        return {row[0]: row[1] for row in self.connection.execute("SELECT entry_id, title FROM search_index")}

    def tags_by_entry(self) -> Dict[str, List[str]]:
        tags: Dict[str, List[str]] = {}
        for entry_id, tag in self.connection.execute("SELECT entry_id, tag FROM entry_tags ORDER BY entry_id, tag"):
            tags.setdefault(entry_id, []).append(tag)
        return tags

    def list_tags(self) -> List[Tuple[str, int]]:
        """(tag, number of entries), most used first."""
        rows = self.connection.execute("SELECT tag, COUNT(*) AS uses FROM entry_tags GROUP BY tag ORDER BY uses DESC, tag")
        return [(row[0], row[1]) for row in rows]


def _descending(day: str) -> Tuple[int, ...]:
    """Sort key putting later days first."""
    return tuple(-int(part) for part in day.split("-"))

