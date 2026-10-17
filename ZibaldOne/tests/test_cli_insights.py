"""CLI of search, links, graph, stats and reviews (0.1.2–0.1.4), registered like in cli/app.py."""

import json
from datetime import date, timedelta

import pytest
import typer
from typer.testing import CliRunner

from zibaldone.cli.graph_cmd import graph_command
from zibaldone.cli.search_cmd import SEARCH_CONTEXT, links_command, search_command
from zibaldone.cli.stats_cmd import review_command, stats_command
from zibaldone.core.packs import apply_install, find_builtin_pack, plan_install
from zibaldone.core.privacy import NOTICE_VERSION
from zibaldone.storage.database import Store
from zibaldone.storage.paths import data_dir
from zibaldone.storage.settings import record_consent

app = typer.Typer()
app.command("search", context_settings=SEARCH_CONTEXT)(search_command)
app.command("links")(links_command)
app.command("graph")(graph_command)
app.command("stats")(stats_command)
app.command("review")(review_command)
runner = CliRunner()
TODAY = date.today()


def invoke(*args: str):
    return runner.invoke(app, list(args))


def day(offset: int) -> str:
    return (TODAY - timedelta(days=offset)).isoformat()


@pytest.fixture
def data():
    record_consent(data_dir(), accepted=True, notice_version=NOTICE_VERSION)
    with Store.open(data_dir()) as store:
        for name in ("diario", "persone", "collezioni"):
            apply_install(plan_install(find_builtin_pack(name), store), store)
        marco = store.add_entry("persona", {"nome": "Marco Rossi", "soprannomi": ["Marco"]}, day="2026-01-01")
        dinner = store.add_entry("incontro", {"titolo": "Cena al lago", "con": [marco.id], "cosa": "Si parla di perché."}, day=day(1))
        evening = store.add_entry("sera", {"umore": "🙂 Buono", "voto": 7, "fatto": "Visto [[Marco]] e [[Giulia]].", "domani": ["comprare pane"]}, day=day(0))
        mention = store.add_entry("riflessione", {"titolo": "Pensieri", "testo": "Marco ha ragione."}, day=day(2))
        store.add_entry("aree", {"salute": 8, "finanze": 3, "lavoro": 6}, day=day(0))
        store.add_entry("libro", {"titolo": "Dune", "stato": {"status": "ongoing", "current": 10, "total": 100}}, day=day(3))
    return {"marco": marco, "dinner": dinner, "evening": evening, "mention": mention}


def test_search(data) -> None:
    result = invoke("search", "perche")
    assert result.exit_code == 0, result.output
    assert "Zetesis · 1 voce per «perche»" in result.output
    assert "Cena al lago" in result.output and "Si parla di perché." in result.output
    assert "\x1b[" not in result.output  # colours only on a real terminal
    marco = invoke("search", "marco", "--template", "sera")
    assert "Esame serale" in marco.output and "Cena al lago" not in marco.output
    limited = invoke("search", "marco", "--limit", "1")
    assert "Mostro 1 voci su" in limited.output
    assert "nessuna parola da cercare" in invoke("search", "🙂 ***").output
    assert "Nessuna voce trovata" in invoke("search", "zzzz").output
    unquoted = invoke("search", "cena", "lago", "-tutto", "-perch*")
    assert unquoted.exit_code == 0 and "Nessuna voce trovata" in unquoted.output
    assert "Cena al lago" in invoke("search", "cena", "-tutto").output
    listed = invoke("search", "--tag", "nessuna")
    assert listed.exit_code == 0 and "Nessuna voce trovata" in listed.output
    missing = invoke("search", "x", "--template", "nessuno")
    assert missing.exit_code == 1 and "non esiste un modello" in missing.output
    bad_day = invoke("search", "x", "--since", "domani l'altro")
    assert bad_day.exit_code == 1 and "data non valida" in bad_day.output


def test_search_fallback_says_so(data, monkeypatch) -> None:
    monkeypatch.setenv("ZIBALDONE_NO_FTS", "1")
    result = invoke("search", "perche")
    assert "Cena al lago" in result.output and "ricerca semplice" in result.output


def test_links(data) -> None:
    result = invoke("links", data["marco"].id[:6])
    assert result.exit_code == 0, result.output
    assert result.output.startswith("Marco Rossi\n")
    assert "Citata da (2):" in result.output
    assert "← Cena al lago" in result.output and "nel blocco «Con chi»" in result.output
    assert "citato in «Cosa ho fatto»" in result.output
    assert "La nominano senza collegamento (1):" in result.output and "Pensieri" in result.output
    outgoing = invoke("links", data["evening"].id)
    assert "Collega (2):" in outgoing.output and "→ Marco Rossi" in outgoing.output
    assert "→ [[Giulia]]" in outgoing.output and "si collegherà da solo" in outgoing.output
    quiet = invoke("links", data["marco"].id, "--no-mentions")
    assert "senza collegamento" not in quiet.output
    assert invoke("links", "zzzz").exit_code == 1


def test_graph_exports(data, tmp_path) -> None:
    page, raw = tmp_path / "grafo.html", tmp_path / "grafo.json"
    result = invoke("graph", "--html", str(page), "--json", str(raw), "--unresolved")
    assert result.exit_code == 0, result.output
    assert "Rizoma · 6 voci, 3 collegamenti" in result.output
    assert "Le più collegate: " in result.output and "Marco Rossi (2)" in result.output
    assert page.read_text(encoding="utf-8").startswith("<!doctype html>")
    data_out = json.loads(raw.read_text(encoding="utf-8"))
    assert any(node["kind"] == "missing" and node["label"] == "Giulia" for node in data_out["nodes"])
    around = invoke("graph", "--around", data["marco"].id[:6], "--depth", "1")
    assert "Rizoma · 3 voci" in around.output
    assert invoke("graph", "--around", "zzzz").exit_code == 1
    nowhere = invoke("graph", "--html", str(tmp_path / "manca" / "g.html"))
    assert nowhere.exit_code == 1 and "non esiste" in nowhere.output
    assert "Nessuna voce" in invoke("graph", "--template", "anno").output


def test_stats(data, tmp_path) -> None:
    result = invoke("stats")
    assert result.exit_code == 0, result.output
    assert result.output.startswith("Theoria · settimana")
    for text in ("Scrittura", "Umore (da 1 a 5)", "Aree della vita", "Voto alla giornata (Esame serale): 7 su 10", "Dune", "comprare pane"):
        assert text in result.output
    month = invoke("stats", "--month", "--date", TODAY.isoformat(), "--html", str(tmp_path / "theoria.html"))
    assert month.exit_code == 0 and "sett." in month.output
    assert (tmp_path / "theoria.html").exists()
    assert invoke("stats", "--week", "--month").exit_code == 1
    empty = invoke("stats", "--date", "2020-01-01")
    assert "Nessuna voce in questo periodo." in empty.output


def test_review_proposes_and_saves_once(data) -> None:
    result = invoke("review", "week", "--save")
    assert result.exit_code == 0, result.output
    assert "Hypomnemata · revisione della settimana" in result.output
    assert "Proposta per «Hypomnemata»" in result.output and "Area su cui concentrarmi: Finanze" in result.output
    assert "Revisione salvata" in result.output
    with Store.open(data_dir()) as store:
        saved = store.list_entries(template="settimana")
        assert len(saved) == 1 and saved[0].values["obiettivi"] == [{"text": "comprare pane", "done": False}]
    again = invoke("review", "settimana", "--save")
    assert "C'è già una revisione per questo periodo" in again.output
    month = invoke("review", "mese")
    assert "Lettera a Lucilio" in month.output and "Proposta per «Lettera a Lucilio»" in month.output
    wrong = invoke("review", "anno")
    assert wrong.exit_code == 1 and "week" in wrong.output


def test_review_without_review_templates(tmp_path) -> None:
    record_consent(data_dir(), accepted=True, notice_version=NOTICE_VERSION)
    result = invoke("review", "week")
    assert result.exit_code == 0, result.output
    assert "zbone pack install diario" in result.output
