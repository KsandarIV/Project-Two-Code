"""Zetesis (la ricerca): query parsing, text normalisation, documents and snippets.

Pure functions only; the SQL lives in `storage/database.py`. The same
normaliser feeds the FTS5 index and the LIKE fallback, so both engines find
the same words, ignoring case and accents ("perché" finds "perche").

Query syntax (user input is never passed to FTS5 as is):
    parole semplici   all words must appear (AND)
    "frase esatta"    the words in this order
    parol*            words starting with "parol"
    -parola           entries without this word (also -"frase")
"""

import math
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from zibaldone.core.templates import Entry, Template

TOKEN = re.compile(r"[^\W_]+")
CHUNK = re.compile(r'(-*)"([^"]*)"?|(\S+)')
MAX_TERMS = 32
MAX_WORDS_PER_TERM = 12
SNIPPET_WORDS = 24
ENGINE_FTS = "fts5"
ENGINE_LIKE = "like"
# Weights of title, body and tags, for bm25() and for the fallback score.
FIELD_WEIGHTS = (5.0, 1.0, 3.0)
# Block types whose text goes into the body (the title and tags have their own fields).
BODY_TYPES = {"text", "longtext", "bookmark", "choice", "checklist", "link"}


def fold(text: str) -> str:
    """Lower case without accents: 'Perché' -> 'perche'."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char)).lower()


def words(text: str) -> List[str]:
    """The searchable words of a text, folded (letters and digits; the rest separates)."""
    return TOKEN.findall(fold(unicodedata.normalize("NFC", text)))


def normalized(text: str) -> str:
    return " ".join(words(text))


# — queries —


@dataclass(frozen=True)
class Term:
    """One part of a query: a word or a phrase, maybe a prefix, maybe excluded."""

    words: Tuple[str, ...]
    prefix: bool = False
    exclude: bool = False

    def fts(self) -> str:
        # Only letters and digits ever reach FTS5, always inside quotes.
        return '"' + " ".join(self.words) + '"' + ("*" if self.prefix else "")

    def like(self) -> str:
        # The normalised text has a space before and after every word.
        return "% " + escape_like(" ".join(self.words)) + ("%" if self.prefix else " %")

    def __str__(self) -> str:
        text = " ".join(self.words) + ("*" if self.prefix else "")
        if len(self.words) > 1:
            text = f'"{text}"'
        return ("-" if self.exclude else "") + text


@dataclass(frozen=True)
class Query:
    text: str
    terms: Tuple[Term, ...] = ()

    @property
    def include(self) -> Tuple[Term, ...]:
        return tuple(term for term in self.terms if not term.exclude)

    @property
    def exclude(self) -> Tuple[Term, ...]:
        return tuple(term for term in self.terms if term.exclude)

    @property
    def blank(self) -> bool:
        """Nothing typed: only the filters apply."""
        return not self.text.strip()

    @property
    def unusable(self) -> bool:
        """Something typed, but no word in it (only symbols or emoji)."""
        return not self.blank and not self.terms

    def fts_match(self) -> str:
        return " ".join(term.fts() for term in self.include)

    def fts_exclusion(self) -> str:
        return " OR ".join(term.fts() for term in self.exclude)

    def __str__(self) -> str:
        return " ".join(str(term) for term in self.terms)


def parse_query(text: str) -> Query:
    """Turn what the user typed into terms. Never fails: odd input just yields fewer terms."""
    text = text or ""
    terms: List[Term] = []
    for match in CHUNK.finditer(text):
        dashes, phrase, plain = match.groups()
        if plain is not None:
            exclude = plain.startswith("-") and len(plain.lstrip("-")) > 0
            body = plain.lstrip("-") if exclude else plain
            prefix = body.endswith("*")
        else:
            exclude = bool(dashes)
            body = phrase
            prefix = phrase.rstrip().endswith("*")
        found = words(body)[:MAX_WORDS_PER_TERM]
        if not found:
            continue
        term = Term(tuple(found), prefix=prefix, exclude=exclude)
        if term not in terms:
            terms.append(term)
        if len(terms) >= MAX_TERMS:
            break
    return Query(text=text, terms=tuple(terms))


# — documents: what gets indexed for one entry —


@dataclass
class Document:
    title: str
    name: str
    body: str
    tags: List[str] = field(default_factory=list)

    @property
    def tags_text(self) -> str:
        return ", ".join(self.tags)

    def norm(self) -> str:
        """Folded words of title, body and tags, each word between spaces (for LIKE)."""
        parts = [normalized(self.name), normalized(self.body), normalized(self.tags_text)]
        return " " + " \n ".join(parts) + " "


def entry_document(entry: Entry, template: Template, linked_titles: Optional[Dict[str, str]] = None) -> Document:
    """Title (display and real), body and tags of an entry, for the index.

    `linked_titles` maps entry ids to titles, so that an encounter linked to
    Marco is found by searching "Marco".
    """
    linked_titles = linked_titles or {}
    title_key = template.title_key
    name = str(entry.values.get(title_key, "")) if title_key else ""
    prose: List[str] = []
    extra: List[str] = []  # lists and choices come after the prose, so snippets start with what was written
    tags: List[str] = []
    for spec in template.blocks:
        if spec.key not in entry.values:
            continue
        value = entry.values[spec.key]
        if spec.type == "tags":
            tags.extend(tag for tag in value if tag not in tags)
            continue
        if spec.key == title_key or spec.type not in BODY_TYPES:
            continue
        if spec.type == "checklist":
            extra.append("; ".join(item["text"] for item in value))
        elif spec.type == "choice":
            extra.append(str(value))
        elif spec.type == "link":
            titles = [linked_titles[item] for item in value if item in linked_titles]
            if titles:
                prose.append(", ".join(titles))
        else:
            prose.append(str(value))
    return Document(title=entry.title(template), name=name, body="\n".join(prose + extra), tags=tags)


def display_text(body: str) -> str:
    """Body text for snippets: line and block breaks shown as ' · '."""
    return re.sub(r"\s*\n\s*", " · ", body.strip())


# — snippets and scores —


@dataclass(frozen=True)
class Snippet:
    """A piece of text and the (start, end) ranges of the words that matched."""

    text: str
    highlights: Tuple[Tuple[int, int], ...] = ()

    def marked(self, before: str = "[", after: str = "]") -> str:
        parts, last = [], 0
        for start, end in self.highlights:
            parts += [self.text[last:start], before, self.text[start:end], after]
            last = end
        parts.append(self.text[last:])
        return "".join(parts)

    def __bool__(self) -> bool:
        return bool(self.text)


def _spans(text: str) -> List[Tuple[int, int, str]]:
    spans = []
    for match in TOKEN.finditer(text):
        for word in TOKEN.findall(fold(match.group())):
            spans.append((match.start(), match.end(), word))
    return spans


def _matches(spans: Sequence[Tuple[int, int, str]], terms: Sequence[Term]) -> List[Tuple[int, int]]:
    """(token position, term index) for every token covered by a term occurrence."""
    hits: List[Tuple[int, int]] = []
    for index, term in enumerate(terms):
        size = len(term.words)
        for start in range(len(spans) - size + 1):
            ok = True
            for offset, wanted in enumerate(term.words):
                word = spans[start + offset][2]
                last = offset == size - 1
                if not (word == wanted or (last and term.prefix and word.startswith(wanted))):
                    ok = False
                    break
            if ok:
                hits.extend((start + offset, index) for offset in range(size))
    return hits


def make_snippet(text: str, query: Query, width: int = SNIPPET_WORDS, whole: bool = False) -> Snippet:
    """The best window of about `width` words, with the matched words highlighted.

    With whole=True the full text is kept (used for titles).
    """
    clean = " ".join(text.split())
    spans = _spans(clean)
    if not spans:
        return Snippet(clean[:200])
    hits = _matches(spans, query.include)
    marked = sorted({position for position, _ in hits})
    if whole or len(spans) <= width:
        first, last = 0, len(spans)
    else:
        best: Tuple[int, int, int] = (-1, -1, 0)
        for position in marked or [0]:
            start = max(0, min(position - 4, len(spans) - width))
            inside = [(p, t) for p, t in hits if start <= p < start + width]
            score = (len({t for _, t in inside}), len({p for p, _ in inside}), -start)
            if score > best:
                best, first = score, start
        last = min(len(spans), first + width)
    begin = 0 if first == 0 or whole else spans[first][0]
    end = len(clean) if last == len(spans) or whole else spans[last - 1][1]
    prefix = "" if begin == 0 else "…"
    suffix = "" if end == len(clean) else "…"
    out = prefix + clean[begin:end] + suffix
    shift = len(prefix) - begin
    ranges: List[List[int]] = []
    for position in marked:
        if not first <= position < last:
            continue
        start, stop = spans[position][0] + shift, spans[position][1] + shift
        if ranges and out[ranges[-1][1]:start].strip() == "" and start - ranges[-1][1] <= 1:
            ranges[-1][1] = max(ranges[-1][1], stop)
        elif ranges and start < ranges[-1][1]:
            continue
        else:
            ranges.append([start, stop])
    return Snippet(out, tuple((start, stop) for start, stop in ranges))


def fallback_score(norm: str, query: Query) -> float:
    """Rank for the LIKE engine, from the normalised text: weighted matches, damped for long bodies."""
    fields = [" " + part.strip() + " " for part in (norm.split(" \n ") + ["", "", ""])[:3]]
    title, body, tags = fields
    title_weight, body_weight, tags_weight = FIELD_WEIGHTS
    score = 0.0
    for term in query.include:
        needle = " " + " ".join(term.words) + ("" if term.prefix else " ")
        score += title_weight * title.count(needle) + tags_weight * tags.count(needle) + body_weight * min(body.count(needle), 10)
    return round(score / (1.0 + math.log1p(body.count(" ") / 100.0)), 6)


# — results —


@dataclass
class SearchHit:
    entry: Entry
    title: str
    title_highlights: Tuple[Tuple[int, int], ...]
    snippet: Snippet
    rank: float

    @property
    def template(self) -> str:
        return self.entry.template


@dataclass
class SearchResult:
    query: Query
    hits: List[SearchHit]
    engine: str
    total: int

    @property
    def fts(self) -> bool:
        """True when SQLite FTS5 answered, False for the LIKE fallback."""
        return self.engine == ENGINE_FTS

    def __len__(self) -> int:
        return len(self.hits)

    def __iter__(self):
        return iter(self.hits)


def escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
