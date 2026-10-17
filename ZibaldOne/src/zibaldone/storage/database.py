"""SQLite storage for templates and entries, with numbered migrations.

The database lives in the data folder as `zibaldone.db`. `PRAGMA user_version`
records which migrations ran; a newer app adds migrations, never edits old ones.
"""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence

from zibaldone.core.templates import Entry, Template, now_iso, validate_values
from zibaldone.core.blocks import parse_day

DATABASE_FILE = "zibaldone.db"

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
)


class StoreError(Exception):
    """A storage operation was refused (missing item, conflict, …)."""


def database_path(folder: Path) -> Path:
    return folder / DATABASE_FILE


class Store:
    """Access to templates and entries. Use as a context manager."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.connection = sqlite3.connect(str(path))
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.migrate()

    @classmethod
    def open(cls, folder: Path) -> "Store":
        return cls(database_path(folder))

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
                cursor.executescript("BEGIN;" + MIGRATIONS[number - 1] + f"; PRAGMA user_version = {number};")

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
        exists = self.find_template(template.slug) is not None
        if exists and not replace:
            raise StoreError(f"esiste già un modello '{template.slug}'")
        timestamp = now_iso()
        with self.transaction() as cursor:
            if exists:
                cursor.execute("UPDATE templates SET data = ?, updated_at = ? WHERE slug = ?", (data, timestamp, template.slug))
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
        )

    def add_entry(self, template_slug: str, values: Dict[str, Any], day: Optional[str] = None) -> Entry:
        template = self.get_template(template_slug)
        entry = Entry.new(template, values, day)
        with self.transaction() as cursor:
            cursor.execute(
                "INSERT INTO entries (id, template, day, data, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (entry.id, entry.template, entry.day, json.dumps(entry.values, ensure_ascii=False), entry.created_at, entry.updated_at),
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
    ) -> List[Entry]:
        clauses, params = [], []
        if template:
            clauses.append("template = ?")
            params.append(template)
        if day_from:
            clauses.append("day >= ?")
            params.append(parse_day(day_from))
        if day_to:
            clauses.append("day <= ?")
            params.append(parse_day(day_to))
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        order = "DESC" if newest_first else "ASC"
        sql = f"SELECT * FROM entries {where} ORDER BY day {order}, created_at {order}"
        if limit:
            sql += f" LIMIT {int(limit)}"
        return [self._entry_from_row(row) for row in self.connection.execute(sql, params).fetchall()]

    def update_entry(self, reference: str, values: Dict[str, Any], day: Optional[str] = None, merge: bool = True) -> Entry:
        """Change an entry. With merge=True, only the given blocks change; None clears a block."""
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
        entry.updated_at = now_iso()
        with self.transaction() as cursor:
            cursor.execute(
                "UPDATE entries SET data = ?, day = ?, updated_at = ? WHERE id = ?",
                (json.dumps(entry.values, ensure_ascii=False), entry.day, entry.updated_at, entry.id),
            )
        self.after_entry_saved(entry, template)
        return entry

    def delete_entry(self, reference: str) -> Entry:
        entry = self.get_entry(reference)
        with self.transaction() as cursor:
            cursor.execute("DELETE FROM entries WHERE id = ?", (entry.id,))
        self.after_entry_deleted(entry)
        return entry

    # — hooks for indexes added by later versions (links, search) —

    def after_entry_saved(self, entry: Entry, template: Template) -> None:
        """Keep secondary indexes in sync. Extended from v0.1.2."""

    def after_entry_deleted(self, entry: Entry) -> None:
        """Keep secondary indexes in sync. Extended from v0.1.2."""
