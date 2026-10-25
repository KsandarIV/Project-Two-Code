import json
from pathlib import Path
from types import SimpleNamespace

import flet as ft

from zibaldone.ui import novita, sparkles
from zibaldone.ui.app import Shell
from tests.test_ui_views import FakePage, folder, ready, texts, walk  # noqa: F401,F811


def test_releases_are_read_newest_first_and_a_broken_file_is_skipped(tmp_path: Path) -> None:
    folder = tmp_path / "novita"
    folder.mkdir()
    for version in ("0.2.9", "0.2.10", "0.2.2"):
        (folder / f"{version}.json").write_text(json.dumps({"versione": version, "data": "2026-10-24", "titolo": "T", "voci": [{"tipo": "nuovo", "testo": "x"}]}), encoding="utf-8")
    (folder / "rotto.json").write_text("{", encoding="utf-8")
    assert [release.version for release in novita.load_releases(tmp_path)] == ["0.2.10", "0.2.9", "0.2.2"]
    assert novita.load_releases(tmp_path / "niente") == []


def test_the_real_notes_load_and_the_button_stays_lit_until_they_are_opened(ready: Path) -> None:
    releases = novita.load_releases()
    assert releases and releases[0].items
    assert novita.has_unseen(ready, releases)
    shell = Shell(FakePage(), ready)
    shell.start("/oggi")
    assert any(item.tooltip == "Novità" for item in walk(shell.body.content) if isinstance(item, ft.Container))
    shell.navigate("/novita")
    assert releases[0].version in " ".join(texts(shell.body.content))
    assert not novita.has_unseen(ready, releases)


def test_the_sparkles_are_dimmer_once_seen_and_on_a_wide_screen() -> None:
    lit = sparkles.sparkle_button(lambda _: None, unseen=True, wide=False)
    seen = sparkles.sparkle_button(lambda _: None, unseen=False, wide=False)
    wide = sparkles.sparkle_button(lambda _: None, unseen=True, wide=True)
    assert lit.data["level"] > seen.data["level"] and lit.data["level"] > wide.data["level"]
