"""Import from the files other services export (0.2.5): Goodreads, Letterboxd, MyAnimeList, Steam.

Only from a file the user hands over, never through an account or an API of
those services (docs/tecnica/requisiti-v0.2.md, conflict 2). Reading a file is
pure (`parse_*` give `ImportItem`s); `import_items` writes them through a Store.

Votes are mapped to the stars of the Museion templates (5 stars, half points);
the Goodreads, Letterboxd and MyAnimeList dates become the start and finish dates.
"""

import csv
import gzip
import html
import io
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

MAX_IMPORT_BYTES = 50 * 1024 * 1024
MAX_IMPORT_ITEMS = 20_000
READ_SHELVES = ("read", "to-read", "currently-reading")
FAVORITE_SHELVES = ("favorites", "favourites", "preferiti")


class ImportFileError(Exception):
    """The file is not what the chosen service exports. Messages are for the user."""


@dataclass(frozen=True)
class ImportItem:
    template: str  # the Museion template the entry goes in: libro, film, anime, videogioco
    values: Dict[str, Any]
    day: str = ""  # the day the entry is about (when it was finished or last played); "" is today

    @property
    def title(self) -> str:
        return str(self.values.get("titolo", ""))


@dataclass
class Parsed:
    source: str
    items: List[ImportItem] = field(default_factory=list)
    problems: List[str] = field(default_factory=list)  # rows that could not be read


# * — reading the file —


def decode(data: bytes) -> str:
    """The text of an export: plain, UTF-8 with or without BOM, or gzip (MyAnimeList sends .xml.gz)."""
    if len(data) > MAX_IMPORT_BYTES:
        raise ImportFileError("il file è troppo grande (massimo 50 MB)")
    if data[:2] == b"\x1f\x8b":
        try:
            data = gzip.decompress(data)
        except (OSError, EOFError):
            raise ImportFileError("il file compresso è rovinato") from None
        if len(data) > MAX_IMPORT_BYTES:
            raise ImportFileError("il file è troppo grande (massimo 50 MB)")
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ImportFileError("non riesco a leggere il testo del file")


def read_path(path: Path) -> bytes:
    """The bytes of an export file, refusing the ones that are too big before reading them."""
    try:
        if path.stat().st_size > MAX_IMPORT_BYTES:
            raise ImportFileError("il file è troppo grande (massimo 50 MB)")
        return path.read_bytes()
    except OSError as error:
        raise ImportFileError(f"non riesco a leggere «{path.name}»: {error.strerror or error}") from None


def _csv_rows(data: bytes, required: tuple, what: str) -> List[Dict[str, str]]:
    reader = csv.DictReader(io.StringIO(decode(data)))
    names = [(name or "").strip() for name in (reader.fieldnames or [])]
    missing = [name for name in required if name not in names]
    if missing:
        raise ImportFileError(f"non sembra un file di {what}: mancano le colonne {', '.join(missing)}")
    reader.fieldnames = names
    rows = []
    try:
        for row in reader:
            rows.append({key: (value or "").strip() for key, value in row.items() if key})
            if len(rows) > MAX_IMPORT_ITEMS:
                raise ImportFileError(f"troppe righe (massimo {MAX_IMPORT_ITEMS})")
    except csv.Error as error:
        raise ImportFileError(f"il file non è un CSV valido: {error}") from None
    return rows


def _plain(text: str) -> str:
    folded = unicodedata.normalize("NFKD", (text or "").lower())
    return " ".join("".join(char for char in folded if not unicodedata.combining(char)).split())


def _clean(text: Any) -> str:
    return " ".join(html.unescape(str(text or "")).split())


def _review(text: Any) -> str:
    """Review text with the `<br/>` and tags of the web page turned into plain lines."""
    text = re.sub(r"<br\s*/?>", "\n", str(text or ""), flags=re.IGNORECASE)
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    return "\n".join(line.strip() for line in text.replace("\r\n", "\n").split("\n")).strip()


def _int(text: Any) -> int:
    match = re.search(r"\d+", str(text or ""))
    return int(match.group()) if match else 0


def _day(text: Any) -> str:
    """'2024/05/12', '2024-05-12' or '2024-05-12 20:01:00' -> '2024-05-12'; '' when empty or invalid (also 0000-00-00)."""
    match = re.match(r"^\s*(\d{4})[-/](\d{2})[-/](\d{2})", str(text or ""))
    if not match:
        return ""
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3))).isoformat()
    except ValueError:
        return ""


def _progress(status: str, current: Optional[float] = None, total: Optional[float] = None, started: str = "", finished: str = "") -> Dict[str, Any]:
    value: Dict[str, Any] = {"status": status}
    if total:
        value["total"] = total
    if current:
        value["current"] = min(current, total) if total else current
    if started:
        value["started"] = started
    if finished and status == "completed":
        value["finished"] = finished
    return value


# * — Goodreads —


def parse_goodreads(data: bytes, filename: str = "") -> Parsed:
    """The CSV of My Books → Import and export → Export Library."""
    parsed = Parsed("goodreads")
    status_of = {"read": "completed", "currently-reading": "ongoing", "to-read": "wishlist"}
    for number, row in enumerate(_csv_rows(data, ("Title",), "Goodreads"), start=2):
        title = _clean(row.get("Title"))
        if not title:
            parsed.problems.append(f"riga {number}: manca il titolo")
            continue
        values: Dict[str, Any] = {"titolo": title}
        if _clean(row.get("Author")):
            values["autore"] = _clean(row["Author"])
        shelf = row.get("Exclusive Shelf", "").lower()
        finished = _day(row.get("Date Read"))
        if shelf in status_of:
            values["stato"] = _progress(status_of[shelf], total=_int(row.get("Number of Pages")) or None, finished=finished)
        rating = _int(row.get("My Rating"))
        if 1 <= rating <= 5:
            values["voto"] = rating
        shelves = [name.strip() for name in row.get("Bookshelves", "").split(",") if name.strip()]
        genres = [name for name in shelves if name.lower() not in READ_SHELVES + FAVORITE_SHELVES]
        if genres:
            values["generi"] = genres
        if any(name.lower() in FAVORITE_SHELVES for name in shelves):
            values["preferito"] = True
        review = _review(row.get("My Review"))
        if review:
            spoiler = row.get("Spoiler", "").lower() in ("true", "yes", "1")
            values["recensione_spoiler" if spoiler else "recensione"] = review
        isbn = re.sub(r"[^0-9Xx]", "", row.get("ISBN13") or row.get("ISBN") or "")
        if isbn:
            values["isbn"] = isbn
        parsed.items.append(ImportItem("libro", values, finished or _day(row.get("Date Added"))))
    return parsed


# * — Letterboxd —


def parse_letterboxd(data: bytes, filename: str = "") -> Parsed:
    """A CSV from the Letterboxd export: ratings, reviews, diary, watched or (by its name) watchlist."""
    parsed = Parsed("letterboxd")
    wish = "watchlist" in filename.lower()
    for number, row in enumerate(_csv_rows(data, ("Name", "Year"), "Letterboxd"), start=2):
        title = _clean(row.get("Name"))
        if not title:
            parsed.problems.append(f"riga {number}: manca il titolo")
            continue
        values: Dict[str, Any] = {"titolo": title}
        year = _int(row.get("Year"))
        if 1880 <= year <= 2100:
            values["anno"] = year
        watched = _day(row.get("Watched Date")) or _day(row.get("Date"))
        values["stato"] = _progress("wishlist") if wish else _progress("completed", finished=watched)
        try:
            rating = float(row.get("Rating", "").replace(",", "."))
        except ValueError:
            rating = 0.0
        if 0.5 <= rating <= 5 and rating * 2 == int(rating * 2):
            values["voto"] = int(rating) if rating == int(rating) else rating
        review = _review(row.get("Review"))
        if review:
            values["recensione"] = review
        tags = [tag.strip() for tag in row.get("Tags", "").split(",") if tag.strip()]
        if tags:
            values["generi"] = tags
        parsed.items.append(ImportItem("film", values, "" if wish else watched))
    return parsed


# * — MyAnimeList —

MAL_STATUS = {"watching": "ongoing", "completed": "completed", "on-hold": "paused", "dropped": "dropped", "plan to watch": "wishlist"}


def parse_myanimelist(data: bytes, filename: str = "") -> Parsed:
    """The XML of the anime list export (also gzip-compressed)."""
    parsed = Parsed("myanimelist")
    text = decode(data)
    if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
        raise ImportFileError("il file XML ha una struttura che non accetto: scarica di nuovo l'esportazione da MyAnimeList")
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        raise ImportFileError("non è un file XML di MyAnimeList") from None
    if root.tag != "myanimelist":
        raise ImportFileError("non è un file XML di MyAnimeList")
    for number, node in enumerate(root.findall("anime"), start=1):
        def get(name: str) -> str:
            return (node.findtext(name) or "").strip()

        title = _clean(get("series_title"))
        if not title:
            parsed.problems.append(f"anime {number}: manca il titolo")
            continue
        values: Dict[str, Any] = {"titolo": title}
        status = MAL_STATUS.get(get("my_status").lower())
        if status:
            started, finished = _day(get("my_start_date")), _day(get("my_finish_date"))
            values["stato"] = _progress(status, _int(get("my_watched_episodes")), _int(get("series_episodes")) or None, started, finished)
        score = _int(get("my_score"))
        if 1 <= score <= 10:
            values["voto"] = score / 2 if score % 2 else score // 2  # 0-10 to 0-5 stars, in half points
        comments = _review(get("my_comments"))
        if comments:
            values["recensione"] = comments
        parsed.items.append(ImportItem("anime", values, _day(get("my_finish_date")) or _day(get("my_start_date"))))
        if len(parsed.items) > MAX_IMPORT_ITEMS:
            raise ImportFileError(f"troppi elementi (massimo {MAX_IMPORT_ITEMS})")
    return parsed


# * — Steam —


def parse_steam(data: bytes, filename: str = "") -> Parsed:
    """The JSON of GetOwnedGames (`{"response": {"games": [...]}}`, or just the list of games)."""
    parsed = Parsed("steam")
    try:
        loaded = json.loads(decode(data))
    except ValueError:
        raise ImportFileError("non è un file JSON di Steam") from None
    inner = loaded.get("response") if isinstance(loaded, dict) and isinstance(loaded.get("response"), dict) else loaded
    games = inner.get("games") if isinstance(inner, dict) else inner
    if not isinstance(games, list):
        raise ImportFileError("non è l'elenco dei giochi di Steam (GetOwnedGames)")
    for number, game in enumerate(games[:MAX_IMPORT_ITEMS], start=1):
        title = _clean(game.get("name")) if isinstance(game, dict) else ""
        if not title:
            parsed.problems.append(f"gioco {number}: manca il nome")
            continue
        values: Dict[str, Any] = {"titolo": title, "piattaforma": "Steam"}
        minutes = game.get("playtime_forever")
        if isinstance(minutes, (int, float)) and not isinstance(minutes, bool) and minutes > 0:
            values["ore"] = round(minutes / 60, 1)
        else:
            values["stato"] = _progress("not_started")
        last = game.get("rtime_last_played")
        day = ""
        if isinstance(last, (int, float)) and not isinstance(last, bool) and last > 0:
            try:
                day = datetime.fromtimestamp(last).date().isoformat()
            except (OverflowError, OSError, ValueError):
                day = ""
        parsed.items.append(ImportItem("videogioco", values, day))
    return parsed


# * — the sources —


@dataclass(frozen=True)
class Source:
    key: str
    name: str
    what: str  # what it brings
    how: str  # how to get the file
    parse: Callable[[bytes, str], Parsed]


SOURCES: Dict[str, Source] = {
    source.key: source
    for source in (
        Source(
            "goodreads", "Goodreads", "libri", "Goodreads → My Books → Import and export → Export Library: serve il file CSV.", parse_goodreads
        ),
        Source(
            "letterboxd", "Letterboxd", "film",
            "Letterboxd → Settings → Import & Export → Export your data: dallo zip scegli un CSV (ratings, reviews, diary, watched o watchlist).",
            parse_letterboxd,
        ),
        Source("myanimelist", "MyAnimeList", "anime", "MyAnimeList → Import/Export: serve il file XML dell'elenco anime (va bene anche .xml.gz).", parse_myanimelist),
        Source(
            "steam", "Steam", "videogiochi",
            "Steam non ha un'esportazione: serve un file JSON con la risposta di GetOwnedGames dell'API di Steam (con include_appinfo=1).",
            parse_steam,
        ),
    )
}


def get_source(name: str) -> Source:
    key = _plain(name).replace(" ", "")
    key = {"mal": "myanimelist"}.get(key, key)
    if key not in SOURCES:
        raise ImportFileError(f"fonte sconosciuta: «{name}». Scegli tra: {', '.join(SOURCES)}")
    return SOURCES[key]


# * — writing —

TEMPLATE_NAMES = {"libro": "Libro", "film": "Film", "anime": "Anime", "videogioco": "Videogioco"}
KIND_NAMES = {"libro": ("libro", "libri"), "film": ("film", "film"), "anime": ("anime", "anime"), "videogioco": ("videogioco", "videogiochi")}
# Two entries are the same item when the titles match and, where both know it, this second field too.
SECOND_KEY = {"libro": "autore", "film": "anno"}


@dataclass
class ImportResult:
    added: Dict[str, int] = field(default_factory=dict)  # per template
    existing: int = 0  # already in the zibaldone, left as they are
    problems: List[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return sum(self.added.values())

    def summary(self, dry_run: bool = False) -> str:
        """'Aggiunti: 12 libri, 1 film. 3 già presenti, lasciati come sono.'"""
        parts = [f"{count} {KIND_NAMES.get(slug, (slug, slug))[count != 1]}" for slug, count in self.added.items()]
        text = f"{'Da aggiungere' if dry_run else 'Aggiunti'}: {', '.join(parts)}." if parts else "Niente di nuovo da aggiungere."
        if self.existing:
            text += f" {self.existing} già presenti, lasciati come sono."
        return text


def _same_item(slug: str, known: Dict[str, Any], new: Dict[str, Any]) -> bool:
    second = SECOND_KEY.get(slug)
    if not second or known.get(second) in (None, "") or new.get(second) in (None, ""):
        return True
    return _plain(str(known[second])) == _plain(str(new[second]))


def import_items(store: Any, items: List[ImportItem], dry_run: bool = False) -> ImportResult:
    """Add the items as entries; those already there (same title) are skipped. `dry_run` only counts."""
    result = ImportResult()
    templates = {slug: store.find_template(slug) for slug in sorted({item.template for item in items})}
    known: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
    for slug, template in templates.items():
        if template is None:
            result.problems.append(f"manca il modello «{TEMPLATE_NAMES.get(slug, slug)}»: installa la Scuola Museion · Collezioni")
            continue
        index: Dict[str, List[Dict[str, Any]]] = {}
        for entry in store.list_entries(template=slug):
            index.setdefault(_plain(str(entry.values.get(template.title_key or "titolo", ""))), []).append(entry.values)
        known[slug] = index
    for item in items:
        template = templates.get(item.template)
        if template is None:
            continue
        title_key = _plain(item.title)
        same = known[item.template].setdefault(title_key, [])
        if any(_same_item(item.template, values, item.values) for values in same):
            result.existing += 1
            continue
        same.append(item.values)  # the same title twice in one file is added once
        if dry_run:
            result.added[item.template] = result.added.get(item.template, 0) + 1
            continue
        keys = {spec.key for spec in template.blocks}
        try:
            store.add_entry(item.template, {key: value for key, value in item.values.items() if key in keys}, day=item.day or None, stamp=False)
        except Exception as error:  # the core and the Store write their messages in Italian
            result.problems.append(f"«{item.title}»: {error}")
            continue
        result.added[item.template] = result.added.get(item.template, 0) + 1
    return result
