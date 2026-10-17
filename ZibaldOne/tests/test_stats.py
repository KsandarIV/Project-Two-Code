from datetime import date

import pytest

from zibaldone.core.links import LinkRecord
from zibaldone.core.packs import find_builtin_pack
from zibaldone.core.stats import (
    area_name,
    best_and_worst_area,
    collections,
    daily_moods,
    in_period,
    month_of,
    monthly_review,
    mood_series,
    mood_summary,
    most_linked_people,
    number,
    open_items,
    period_of,
    propose_review_values,
    render_html,
    review,
    review_template,
    scale_averages,
    streaks,
    trend_words,
    week_of,
    weekly_review,
    writing_activity,
)
from zibaldone.core.templates import BlockSpec, Entry, Template

TEMPLATES = {template.slug: template for name in ("diario", "persone", "collezioni") for template in find_builtin_pack(name).templates}
TODAY = date(2026, 10, 17)  # a Saturday
OTTIMO, BUONO, COSI, GIU = "😄 Ottimo", "🙂 Buono", "😐 Così così", "🙁 Giù"


def make(slug: str, day: str, values: dict, updated: str = "", templates: dict = TEMPLATES) -> Entry:
    entry = Entry.new(templates[slug], values, day)
    entry.created_at = f"{day}T08:00:00+00:00"
    entry.updated_at = updated or f"{day}T12:00:00+00:00"
    return entry


def areas(**scores) -> dict:
    values = {name: 5 for name in ("personale", "salute", "finanze", "famiglia", "sociale", "lavoro", "studio", "svago")}
    values.update(scores)
    return values


@pytest.fixture
def diary():
    marco = make("persona", "2026-01-01", {"nome": "Marco"})
    lucia = make("persona", "2026-01-01", {"nome": "Lucia"})
    monday = make("sera", "2026-10-12", {
        "umore": OTTIMO, "voto": 8, "fatto": "Cena con [[Marco]] al lago. Bellissimo.",
        "domani": [{"text": "chiamare Lucia", "done": False}, {"text": "comprare pane", "done": False}],
    })
    trip = make("incontro", "2026-10-13", {"titolo": "Gita al lago", "con": [marco.id, lucia.id]})
    entries = [
        marco, lucia, monday, trip,
        make("sera", "2026-10-06", {"umore": GIU}),
        make("sera", "2026-10-08", {"umore": COSI, "voto": 4}),
        make("mattina", "2026-10-12", {"umore": BUONO}),
        make("sera", "2026-10-14", {"umore": BUONO, "voto": 6, "imparato": "La pazienza paga. E il resto viene.", "domani": [{"text": "Chiamare  lucia", "done": True}]}),
        make("sera", "2026-10-16", {"umore": COSI}),
        make("aree", "2026-10-13", areas(salute=8, finanze=3)),
        make("aree", "2026-10-15", areas(salute=6, finanze=5)),
        make("libro", "2026-09-01", {"titolo": "Dune", "stato": {"status": "ongoing", "current": 150, "total": 320}, "segnalibro": "pag. 150"}, "2026-10-10T12:00:00+00:00"),
        make("libro", "2026-08-01", {"titolo": "Emma", "stato": {"status": "completed"}}, "2026-09-01T12:00:00+00:00"),
        make("film", "2026-09-20", {"titolo": "Arrival", "stato": {"status": "completed"}}, "2026-10-15T12:00:00+00:00"),
        make("serie", "2026-09-20", {"titolo": "Dark", "stato": {"status": "paused", "current": 5}}, "2026-10-01T12:00:00+00:00"),
    ]
    links = [
        LinkRecord(trip.id, marco.id, "block", "con"),
        LinkRecord(trip.id, lucia.id, "block", "con"),
        LinkRecord(monday.id, marco.id, "wiki", "fatto", "Marco"),
        LinkRecord(monday.id, None, "wiki", "fatto", "Giulia"),
    ]
    return {"entries": entries, "links": links, "marco": marco, "lucia": lucia}


# — periods and words —


def test_periods() -> None:
    week = week_of(TODAY)
    assert (week.start, week.end, week.key) == (date(2026, 10, 12), date(2026, 10, 18), "2026-W42")
    assert week.label == "settimana 42 · 12–18 ottobre 2026"
    assert week_of(date(2026, 10, 1)).label == "settimana 40 · 28 settembre – 4 ottobre 2026"
    new_year = week_of(date(2026, 1, 1))
    assert new_year.key == "2026-W01" and new_year.label == "settimana 1 · 29 dicembre 2025 – 4 gennaio 2026"
    leap = month_of(date(2028, 2, 10))
    assert (leap.end, leap.key, leap.label) == (date(2028, 2, 29), "2028-02", "febbraio 2028")
    assert month_of(date(2026, 1, 5)).previous().label == "dicembre 2025"
    assert week.previous().start == date(2026, 10, 5) and week.next().start == date(2026, 10, 19)
    assert period_of("day", TODAY).label == "sabato 17 ottobre 2026"
    with pytest.raises(ValueError):
        period_of("anno bisestile", TODAY)


def test_number_formatting() -> None:
    assert (number(3.86), number(4.0), number(None), number(7.25, 2)) == ("3,9", "4", "—", "7,25")


# — mood —


def test_mood_from_any_choice_with_values(diary) -> None:
    moods = daily_moods(diary["entries"], TEMPLATES)
    assert moods[date(2026, 10, 12)] == 4.5  # sera 5 and mattina 4 on the same day
    own = Template("umore_mio", "Come sto", [BlockSpec("come", "choice", "Come sto", options={"choices": ["bene", "così", "male"], "values": [10, 5, 0]})])
    plain = Template("tipo", "Tipo", [BlockSpec("tipo", "choice", "Tipo", options={"choices": ["a", "b"]})])
    entries = [make("umore_mio", "2026-10-01", {"come": "bene"}, templates={"umore_mio": own}),
               make("umore_mio", "2026-10-02", {"come": "male"}, templates={"umore_mio": own}),
               make("umore_mio", "2026-10-03", {"come": "così"}, templates={"umore_mio": own}),
               make("tipo", "2026-10-03", {"tipo": "a"}, templates={"tipo": plain})]
    assert daily_moods(entries, {"umore_mio": own, "tipo": plain}) == {date(2026, 10, 1): 5.0, date(2026, 10, 2): 1.0, date(2026, 10, 3): 3.0}


def test_mood_series_and_trend(diary) -> None:
    week = week_of(TODAY)
    days = mood_series(diary["entries"], TEMPLATES, week.start, week.end, "day")
    assert [point.average for point in days] == [4.5, None, 4.0, None, 3.0, None, None]
    weeks = mood_series(diary["entries"], TEMPLATES, date(2026, 10, 1), TODAY, "week")
    assert [(point.key, point.days) for point in weeks] == [("2026-W40", 0), ("2026-W41", 2), ("2026-W42", 3)]
    assert weeks[0].start == date(2026, 10, 1)  # clipped to the range asked
    months = mood_series(diary["entries"], TEMPLATES, date(2026, 9, 1), TODAY, "month")
    assert [point.key for point in months] == ["2026-09", "2026-10"]
    summary = mood_summary(diary["entries"], TEMPLATES, week)
    assert round(summary.average, 3) == 3.833 and summary.previous_average == 2.5
    assert summary.trend == "up" and summary.best_day == date(2026, 10, 12) and summary.worst_day == date(2026, 10, 16)
    assert trend_words(summary, "settimana") == "più su della settimana prima (2,5)"
    previous = mood_summary(diary["entries"], TEMPLATES, week.previous())
    assert previous.trend is None and trend_words(previous, "settimana") == ""


# — scales and areas —


def test_areas_and_other_scales(diary) -> None:
    stats = scale_averages(diary["entries"], TEMPLATES, week_of(TODAY))
    areas_found = [stat for stat in stats if stat.area]
    assert [stat.key for stat in areas_found] == ["personale", "salute", "finanze", "famiglia", "sociale", "lavoro", "studio", "svago"]
    salute = next(stat for stat in areas_found if stat.key == "salute")
    assert (salute.average, salute.count, salute.normalized) == (7.0, 2, 0.7)
    best, worst = best_and_worst_area(stats)
    assert (best.label, worst.label) == ("Salute", "Finanze")
    other = [stat for stat in stats if not stat.area]
    assert [(stat.key, stat.average, stat.template_name) for stat in other] == [("sera.voto", 7.0, "Esame serale")]


def test_areas_by_name_or_by_many_scales() -> None:
    wheel = Template("ruota", "Ruota", [BlockSpec(key, "scale", key.title(), options={"min": 0, "max": 5}) for key in ("corpo", "mente", "soldi", "amici")])
    single = Template("palestra", "Palestra", [BlockSpec("salute", "scale", "Forma"), BlockSpec("fatica", "scale", "Fatica")])
    assert area_name(wheel, wheel.blocks[0]) == "corpo"
    assert area_name(single, single.blocks[0]) == "salute" and area_name(single, single.blocks[1]) is None
    templates = {"ruota": wheel, "palestra": single, "aree": TEMPLATES["aree"]}
    entries = [
        make("ruota", "2026-10-12", {"corpo": 5, "mente": 1, "soldi": 3, "amici": 4}, templates=templates),
        make("palestra", "2026-10-12", {"salute": 4, "fatica": 7}, templates=templates),
        make("aree", "2026-10-13", {"salute": 8}, templates=templates),
    ]
    stats = scale_averages(entries, templates, week_of(TODAY))
    salute = next(stat for stat in stats if stat.key == "salute")
    assert (salute.average, salute.count) == (6.0, 2)  # same area from two templates
    best, worst = best_and_worst_area(stats)
    assert (best.key, worst.key) == ("corpo", "mente")
    level = [make("aree", "2026-10-13", {"salute": 6, "lavoro": 6}, templates=templates)]
    best, worst = best_and_worst_area(scale_averages(level, templates, week_of(TODAY)))
    assert best is not None and worst is None  # all level: no area "needs more care"


# — activity, collections, open items, people —


def test_streaks() -> None:
    days = {date(2026, 10, 15), date(2026, 10, 16)}
    assert streaks(days, TODAY) == (2, 2)  # today has no entry yet: the run is still open
    assert streaks(days | {TODAY, date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 3), date(2026, 10, 4)}, TODAY) == (3, 4)
    assert streaks({date(2026, 10, 10)}, TODAY) == (0, 1)
    assert streaks({date(2026, 10, 20)}, TODAY) == (0, 0)
    assert streaks(set(), TODAY) == (0, 0)


def test_writing_activity(diary) -> None:
    activity = writing_activity(diary["entries"], TEMPLATES, week_of(TODAY), TODAY)
    assert activity.total == 7 and activity.active_days == 5 and activity.days == 7
    assert activity.per_day[date(2026, 10, 12)] == 2
    assert activity.per_template[0] == ("sera", "Esame serale", 3)
    assert (activity.current_streak, activity.longest_streak) == (5, 5)


def test_collections(diary) -> None:
    found = collections(diary["entries"], TEMPLATES, TODAY)
    assert [(item.title, item.status_label, item.percent, item.bookmark) for item in found.in_progress] == [
        ("Dune", "In corso", 47, "pag. 150"), ("Dark", "In pausa", None, ""),
    ]
    assert [item.title for item in found.completed] == ["Arrival"]
    assert [item.title for item in collections(diary["entries"], TEMPLATES, TODAY, recent_days=60).completed] == ["Arrival", "Emma"]


def test_open_items_follow_later_ticks(diary) -> None:
    items = open_items(diary["entries"], TEMPLATES, week_of(TODAY))
    assert [(item.text, item.day, item.block_label) for item in items] == [("comprare pane", date(2026, 10, 12), "Da fare domani")]


def test_most_linked_people(diary) -> None:
    people = most_linked_people(diary["entries"], TEMPLATES, diary["links"], week_of(TODAY))
    assert [(person.title, person.count) for person in people] == [("Marco", 2), ("Lucia", 1)]
    assert most_linked_people(diary["entries"], TEMPLATES, diary["links"], week_of(date(2026, 9, 1))) == []


# — reviews —


def test_weekly_review_and_proposal(diary) -> None:
    result = weekly_review(diary["entries"], TEMPLATES, diary["links"], TODAY, TODAY)
    assert result.entries == 7 and result.previous_entries == 2
    assert result.best_area.label == "Salute" and result.worst_area.label == "Finanze"
    assert [item.title for item in result.completed] == ["Arrival"]
    assert [moment.text for moment in result.moments] == ["Cena con Marco al lago.", "Gita al lago", "Completato: Arrival"]
    template = review_template(TEMPLATES, "week")
    assert template.slug == "settimana"
    values = propose_review_values(result, template)
    assert values == {
        "voto": 7,
        "momenti_belli": "- lun 12: Cena con Marco al lago.\n- mar 13: Gita al lago\n- gio 15: Completato: Arrival",
        "imparato": "- mer 14: La pazienza paga.",
        "area_focus": "Finanze",
        "obiettivi": [{"text": "comprare pane", "done": False}],
    }
    assert "difficolta" not in values  # hard moments are the user's to write


def test_review_leaves_out_review_entries(diary) -> None:
    saved = make("settimana", "2026-10-18", {"voto": 2, "obiettivi": [{"text": "vecchio obiettivo", "done": False}]})
    result = weekly_review(diary["entries"] + [saved], TEMPLATES, diary["links"], TODAY, TODAY)
    assert result.entries == 7
    assert all(stat.key != "settimana.voto" for stat in result.scales)
    assert [item.text for item in result.open_items] == ["comprare pane"]


def test_monthly_review(diary) -> None:
    result = monthly_review(diary["entries"], TEMPLATES, diary["links"], TODAY, TODAY)
    assert result.period.label == "ottobre 2026" and result.previous.label == "settembre 2026"
    assert [point.key for point in result.mood_points] == ["2026-W40", "2026-W41", "2026-W42", "2026-W43", "2026-W44"]
    values = propose_review_values(result, review_template(TEMPLATES, "month"))
    assert values["voto"] == 6 and values["area_focus"] == "Finanze"


def test_without_packs_nothing_breaks() -> None:
    note = Template("nota", "Nota", [BlockSpec("titolo", "text", "Titolo"), BlockSpec("testo", "longtext", "Testo")])
    mine = Template("mia_revisione", "La mia revisione", [
        BlockSpec("punteggio", "scale", "Punteggio", options={"min": 1, "max": 5}),
        BlockSpec("cose_belle", "longtext", "Cose belle"),
        BlockSpec("passi", "checklist", "Prossimi passi"),
    ])
    templates = {"nota": note, "mia_revisione": mine}
    entries = [make("nota", "2026-10-13", {"titolo": "Mostra a Torino", "testo": "Bella."}, templates=templates)]
    result = review(entries, templates, [], "week", TODAY, TODAY)
    assert result.mood.average is None and result.scales == [] and result.best_area is None
    assert review_template(templates, "week") is None
    assert propose_review_values(result, mine) == {"cose_belle": "- mar 13: Mostra a Torino"}
    assert in_period(entries, week_of(TODAY)) == entries
    empty = review([], {}, [], "month", TODAY, TODAY)
    assert empty.entries == 0 and empty.moments == [] and empty.activity.current_streak == 0


def test_stats_html_is_self_contained_and_escaped(diary) -> None:
    entries = diary["entries"] + [make("libro", "2026-09-01", {"titolo": "<b>Libro</b>", "stato": {"status": "ongoing"}})]
    result = weekly_review(entries, TEMPLATES, diary["links"], TODAY, TODAY)
    page = render_html(result, "Hypomnemata", [("Area <x>", "Finanze & co")])
    assert "<b>Libro" not in page and "&lt;b&gt;Libro&lt;/b&gt;" in page and "Area &lt;x&gt;" in page
    assert page.count("<svg") == 4  # mood, writing, areas, other scores
    for forbidden in ("<script src", "<link", "@import", "url(", "https://"):
        assert forbidden not in page
    assert "#0D0E15" in page and "#00E5FF" in page and "Vedi i numeri" in page
