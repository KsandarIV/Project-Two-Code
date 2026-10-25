"""0.2.8 screens: the home from its layout, the tiles, Theoria · Viste and Impostazioni · La tua home."""

from datetime import timedelta
from pathlib import Path

import pytest

ft = pytest.importorskip("flet")

from test_ui_habits import base  # noqa: E402,F401  (fixture)
from test_ui_views import FakePage, button, click, texts, walk  # noqa: E402
from zibaldone.core import home  # noqa: E402
from zibaldone.storage import home_log  # noqa: E402
from zibaldone.core.packs import apply_install, find_builtin_pack, plan_install  # noqa: E402
from zibaldone.core.templates import BlockSpec, Template  # noqa: E402
from zibaldone.storage.database import Store  # noqa: E402
from zibaldone.ui.app import Shell  # noqa: E402
from zibaldone.ui.navigation import SETTINGS_KEYS, parse_route  # noqa: E402
from zibaldone.ui.views import SCREENS  # noqa: E402
from zibaldone.ui.views.tiles import in_days_label  # noqa: E402


def seed(folder: Path, today) -> None:
    with Store.open(folder) as store:
        for name in ("aree", "persone"):
            apply_install(plan_install(find_builtin_pack(name), store), store)
        store.add_entry("persona", {"nome": "Giulia", "compleanno": (today + timedelta(days=3)).replace(year=1990).isoformat()})
        store.add_entry("obiettivo", {"titolo": "Correre 10 km", "stato": {"status": "ongoing", "current": 4, "total": 10}, "scadenza": (today + timedelta(days=20)).isoformat()}, area="salute")
        store.save_template(Template("vista", "Vista", [BlockSpec(key, "text", key) for key in ("nome", "modello", "area", "testo", "campo", "valore", "ordine")], title_block="nome"))
        store.add_entry("persona", {"nome": "Marco"})


def test_routes_and_screens() -> None:
    assert parse_route("/viste").screen == "viste" and parse_route("/viste/abc").arg == "abc" and parse_route("/viste/abc").screen == "vista"
    assert parse_route("/viste/a/b").screen == "oggi"
    assert {"viste", "vista"} <= set(SCREENS) and "home" in SETTINGS_KEYS


def test_in_days_label() -> None:
    assert [in_days_label(n) for n in (0, 1, 5)] == ["oggi", "domani", "tra 5 giorni"]


def test_oggi_follows_the_layout(base: Path) -> None:  # noqa: F811
    shell = Shell(FakePage(), base)
    shell.start("/oggi")
    today = shell.ctx.now().date()
    seed(base, today)
    shell.start("/oggi")
    shown = texts(shell.body.content)
    assert "RICORRENZE" in shown and "Giulia" in shown and "compleanno · tra 3 giorni · 36 anni" in shown
    assert "OBIETTIVI" in shown and any(text.startswith("Salute · tra 20 giorni") or "tra 20 giorni · 40%" in text for text in shown)
    home_log.save_layout(base, home.from_list(["obiettivi", "ricorrenze"]))
    shell.start("/oggi")
    shown = texts(shell.body.content)
    assert shown.index("OBIETTIVI") < shown.index("RICORRENZE") < shown.index("I TRE MOMENTI")  # the moments sit under the grid
    assert "PENSIERO DEL GIORNO" not in shown and "Pensiero del giorno" not in shown
    assert "LE VOCI DI OGGI" in shown


def test_view_tile_and_screens(base: Path) -> None:  # noqa: F811
    shell = Shell(FakePage(), base)
    shell.start("/viste")
    button(shell.body.content, "Installa «Theoria · Viste»")
    seed(base, shell.ctx.now().date())
    shell.start("/viste")
    click(button(shell.body.content, "Nuova vista"))
    dialog = shell.ctx.page.dialogs[-1]
    fields = [item for item in walk(dialog) if isinstance(item, ft.TextField)]
    fields[0].value, fields[1].value = "Persone Marco", "Marco"
    click(button(dialog, "Salva"))
    assert "Vista salvata." in shell.ctx.toasts and "Persone Marco" in texts(shell.body.content)
    with Store.open(base) as store:
        view_id = next(entry.id for entry in store.list_entries(template="vista"))
    home_log.save_layout(base, home.from_list([f"vista:{view_id}", "citazione"]))
    shell.start("/oggi")
    shown = texts(shell.body.content)
    assert "VISTA: PERSONE MARCO" in shown and "Marco" in shown and "Apri la vista" in shown
    shell.start(f"/viste/{view_id}")
    assert "Marco" in texts(shell.body.content)
    shell.start("/viste/nonesiste")
    assert "Questa vista non esiste più." in texts(shell.body.content)
    shell.start("/viste")
    click(next(item for item in walk(shell.body.content) if isinstance(item, ft.IconButton) and item.tooltip == "Togli la vista"))
    click(button(shell.ctx.page.dialogs[-1], "Togli"))
    assert "Vista tolta." in shell.ctx.toasts
    shell.start("/oggi")  # the layout still names the gone view: the tile is just skipped
    assert "VISTA: PERSONE MARCO" not in texts(shell.body.content)


def _tip(shell: Shell, tooltip: str, nth: int = 0) -> ft.IconButton:
    return [item for item in walk(shell.body.content) if isinstance(item, ft.IconButton) and item.tooltip == tooltip][nth]


def test_home_grid_edit_mode_move_resize_hide_add_order_reset(base: Path) -> None:  # noqa: F811
    shell = Shell(FakePage(), base)
    shell.start("/organon/home")
    click(button(shell.body.content, "Modifica la home"))
    assert shell.current.path == "/oggi" and "Modifica la home" in texts(shell.body.content)
    assert home_log.load_layout(base) == home.default_layout()
    click(_tip(shell, "Meno largo", 3))  # abitudini 3x1 -> 2x1
    assert next(p for p in home_log.load_layout(base) if p.key == "abitudini").w == 2
    click(_tip(shell, "A destra", 3))  # now it fits one cell to the right
    assert next(p for p in home_log.load_layout(base) if p.key == "abitudini").col == 1
    click(_tip(shell, "Più largo", 3))  # 3 wide would touch ricorrenze: a notice, nothing changes
    assert next(p for p in home_log.load_layout(base) if p.key == "abitudini").w == 2 and any("sopra" in t for t in shell.ctx.toasts)
    click(_tip(shell, "Nascondi", 0))
    assert "promemoria" not in {p.key for p in home_log.load_layout(base)}
    click(button(shell.body.content, "Aggiungi"))  # the first hidden one comes back where there is room
    assert "promemoria" in {p.key for p in home_log.load_layout(base)}
    click(button(shell.body.content, "Ordina"))
    assert home_log.load_layout(base) == home.compact(home_log.load_layout(base))
    click(button(shell.body.content, "Ripristina"))
    click(button(shell.ctx.page.dialogs[-1], "Ripristina"))
    assert home_log.load_layout(base) == home.default_layout()
    click(button(shell.body.content, "Fine"))
    assert "Modifica la home" not in texts(shell.body.content)


def test_the_grid_follows_the_width_and_drops_empty_rows(base: Path) -> None:  # noqa: F811
    from zibaldone.ui.views import home_grid

    phone = Shell(FakePage(width=412), base)
    phone.start("/oggi")
    stack = next(item for item in walk(phone.body.content) if isinstance(item, ft.Stack) and (item.width or 0) > 100)
    assert stack.width <= 412 - 32 and all(box.left + box.width <= stack.width + 0.01 for box in stack.controls)
    assert home_grid.grid_width(phone.ctx) == 412 - 32


def test_bilancio_tile_is_closed_without_the_pin(base: Path, monkeypatch) -> None:  # noqa: F811
    from zibaldone.core.crypto import ScryptParams
    from zibaldone.storage import keys

    monkeypatch.setattr(keys, "DEFAULT_SCRYPT_PARAMS", ScryptParams(n=2**10))
    shell = Shell(FakePage(), base)
    shell.start("/oggi")
    assert "BILANCIO" not in texts(shell.body.content)  # no finance pack
    with Store.open(base) as store:
        apply_install(plan_install(find_builtin_pack("finanze"), store), store)
    keys.setup_keys(base, "cavallo batteria graffetta")
    with Store.open(base) as store:
        store.add_entry("conto", {"nome": "Carta", "saldo": "1000"})
    shell.start("/oggi")
    shown = texts(shell.body.content)
    assert "BILANCIO" in shown and "Apri con il PIN" in shown and not any("1.000" in text for text in shown)
