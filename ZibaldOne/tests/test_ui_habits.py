"""Askesis screens (0.2.7): Oggi block, /abitudini and the area row."""

from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest

ft = pytest.importorskip("flet")

from test_ui_views import FakePage, button, click, texts  # noqa: E402
from zibaldone.core import habits as H  # noqa: E402
from zibaldone.core.packs import apply_install, find_builtin_pack, plan_install  # noqa: E402
from zibaldone.core.privacy import NOTICE_VERSION  # noqa: E402
from zibaldone.storage.database import Store  # noqa: E402
from zibaldone.storage.settings import record_consent  # noqa: E402
from zibaldone.ui import services  # noqa: E402
from zibaldone.ui.app import Shell  # noqa: E402
from zibaldone.ui.navigation import parse_route  # noqa: E402
from zibaldone.ui.views import SCREENS  # noqa: E402
from zibaldone.ui.views.habits import streak_label  # noqa: E402


@pytest.fixture
def base(isolated_data_dir: Path) -> Path:
    isolated_data_dir.mkdir(parents=True, exist_ok=True)
    record_consent(isolated_data_dir, True, NOTICE_VERSION)
    services.save_ui_settings(isolated_data_dir, diario_suggested=True, backup_files_folder="", app_icon="C")
    with Store.open(isolated_data_dir) as store:
        for name in ("diario", "io", "persone"):
            apply_install(plan_install(find_builtin_pack(name), store), store)
    return isolated_data_dir


def with_habits(folder: Path) -> str:
    with Store.open(folder) as store:
        apply_install(plan_install(find_builtin_pack(H.PACK_NAME), store), store)
        water = store.add_entry(H.HABIT, {"nome": "Acqua", "ogni": H.DAILY, "unita": "bicchieri", "traguardo": 8, "attivo": "Sì"}, area="salute")
        store.add_entry(H.HABIT, {"nome": "Corsa", "ogni": H.WEEKLY, "volte": 3, "attivo": "Sì"}, area="salute")
        store.add_entry(H.HABIT, {"nome": "Pausa", "ogni": H.DAILY, "attivo": "No"}, area="salute")
    return water.id


def test_route_and_screen() -> None:
    route = parse_route("/abitudini")
    assert (route.screen, route.section, route.path) == ("abitudini", "oggi", "/abitudini")
    assert "abitudini" in SCREENS and parse_route("/abitudini/x").screen == "oggi"


def test_streak_label_is_neutral() -> None:
    day = H.Habit("a", "Acqua", "salute", "day", 1, "", None, False, True)
    week = H.Habit("b", "Corsa", "salute", "week", 3, "", None, False, True)
    assert streak_label(day, H.Streak(1, 5, 1, 7, True)) == "1 giorno di fila"
    assert streak_label(day, H.Streak(5, 5, 5, 7, True)) == "5 giorni di fila"
    assert streak_label(week, H.Streak(2, 2, 1, 3, False)) == "2 settimane di fila"
    assert streak_label(day, H.Streak(0, 5, 0, 7, False)) == "nessuna serie in corso"
    assert streak_label(week, H.Streak(0, 2, 1, 3, False)) == "1/3 questa settimana"


def test_screen_installs_marks_and_unmarks(base: Path) -> None:
    shell = Shell(FakePage(), base)
    shell.start("/abitudini")
    click(button(shell.body.content, "Installa «Askesis · Abitudini»"))
    assert "Askesis · Abitudini installato." in shell.ctx.toasts
    assert "Nessun rituale, per ora. Scegline uno piccolo, anche solo un bicchiere d'acqua." in texts(shell.body.content)
    water = with_habits(base)
    shell.ctx.refresh()
    shown = texts(shell.body.content)
    assert "Acqua" in shown and "in pausa" in shown and "nessuna serie in corso · la più lunga: 0" in shown
    click(button(shell.body.content, "Segna"))  # the first «Segna» is Acqua's
    with Store.open(base) as store:
        assert H.practices_of(store, water) == {shell.ctx.now().date(): Decimal("8")}  # the field starts at the goal
    assert "1 giorno di fila · la più lunga: 1" in texts(shell.body.content)
    click(button(shell.body.content, "Togli"))
    with Store.open(base) as store:
        assert H.practices_of(store, water) == {}


def test_today_block_and_area_row(base: Path) -> None:
    shell = Shell(FakePage(), base)
    shell.start("/oggi")
    assert "ABITUDINI DI OGGI" not in texts(shell.body.content)  # no pack, no block
    water = with_habits(base)
    today = shell.ctx.now().date()
    with Store.open(base) as store:
        for back in range(3):
            H.mark(store, water, today - timedelta(days=back), 8)
    shell.start("/oggi")
    shown = texts(shell.body.content)
    assert "ABITUDINI DI OGGI" in shown and "3 giorni di fila" in shown and shown.count("Segna") == 1  # Corsa only; Acqua is done, Pausa inactive
    shell.start("/aree/salute")
    assert "3 giorni di fila" in texts(shell.body.content)
    shell.start("/aree/lavoro")
    assert "Acqua" not in texts(shell.body.content)

