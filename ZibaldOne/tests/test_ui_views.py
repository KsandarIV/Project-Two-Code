"""The screens and the shell, built headless with a stand-in page (needs flet, no window)."""

import asyncio
import dataclasses
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterator, List, Optional

import pytest

ft = pytest.importorskip("flet")

from zibaldone.core.packs import apply_install, find_builtin_pack, plan_install  # noqa: E402
from zibaldone.core.privacy import NOTICE_VERSION  # noqa: E402
from zibaldone.storage import backups  # noqa: E402
from zibaldone.storage.database import Store  # noqa: E402
from zibaldone.storage.settings import load_settings, record_consent, save_settings  # noqa: E402
from zibaldone.ui import services  # noqa: E402
from zibaldone.ui.app import Shell  # noqa: E402
from zibaldone.ui.context import AppContext  # noqa: E402
from zibaldone.ui.navigation import parse_route  # noqa: E402
from zibaldone.ui.views import ONBOARDING_SCREENS, SCREENS  # noqa: E402


class FakePage:
    """Just enough of ft.Page for the shell: attributes, dialogs, tasks run at once."""

    def __init__(self, width: float = 1280) -> None:
        self.width, self.height = width, 800
        self.window = SimpleNamespace()
        self.views = [SimpleNamespace(on_confirm_pop=None)]
        self.controls: List[Any] = []
        self.navigation_bar = None
        self.dialogs: List[Any] = []
        self.route = "/"
        self.updates = 0

    def update(self) -> None:
        self.updates += 1

    def show_dialog(self, dialog: Any) -> None:
        self.dialogs.append(dialog)

    def pop_dialog(self) -> None:
        if self.dialogs:
            self.dialogs.pop()

    def run_task(self, handler, *args):
        coroutine = handler(*args)
        if handler.__name__ in ("reminder_loop", "update_check"):  # long-running or online: tested on their own
            coroutine.close()
            return None
        asyncio.run(coroutine)


def walk(control: Any) -> Iterator[Any]:
    """Every control below `control` (content, controls, actions …), in reading order."""
    seen = set()

    def visit(item: Any) -> Iterator[Any]:
        if id(item) in seen or not isinstance(item, ft.BaseControl):
            return
        seen.add(id(item))
        yield item
        for spec in dataclasses.fields(item):
            if spec.name.startswith("_") or spec.name == "parent":
                continue
            try:
                value = getattr(item, spec.name)
            except Exception:
                continue
            children = value if isinstance(value, (list, tuple)) else [value]
            for child in children:
                yield from visit(child)

    yield from visit(control)


def texts(control: Any) -> List[str]:
    found = []
    for item in walk(control):
        for name in ("value", "content", "label"):
            value = getattr(item, name, None)
            if isinstance(value, str) and value:
                found.append(value)
        for span in getattr(item, "spans", None) or []:
            if getattr(span, "text", None):
                found.append(span.text)
    return found


def button(control: Any, text: str) -> Any:
    for item in walk(control):
        if getattr(item, "content", None) == text and getattr(item, "on_click", None):
            return item
    raise LookupError(f"no button «{text}» in {texts(control)[:30]}")


def click(control: Any) -> None:
    control.on_click(SimpleNamespace(control=control))


@pytest.fixture
def folder(isolated_data_dir: Path) -> Path:
    isolated_data_dir.mkdir(parents=True, exist_ok=True)
    return isolated_data_dir


@pytest.fixture
def ready(folder: Path) -> Path:
    """Consent given, all the packs, a few entries."""
    record_consent(folder, True, NOTICE_VERSION)
    services.save_ui_settings(folder, diario_suggested=True)
    with Store.open(folder) as store:
        for name in ("diario", "collezioni", "io", "persone"):
            apply_install(plan_install(find_builtin_pack(name), store), store)
        giulia = store.add_entry("persona", {"nome": "Giulia"})
        incontro = store.get_template("incontro")
        link = next(spec.key for spec in incontro.blocks if spec.type == "link")
        store.add_entry("incontro", {incontro.title_key: "Cena", link: [giulia.id]})
        store.add_entry("sera", {})
        libro = store.get_template("libro")
        store.add_entry("libro", {libro.title_key: "Ficciones"})
    return folder


def ids(folder: Path) -> dict:
    with Store.open(folder) as store:
        return {entry.template: entry.id for entry in store.list_entries()}


# * — every screen builds —


@pytest.mark.parametrize("wide", [True, False])
def test_every_screen_builds_headless(ready: Path, wide: bool) -> None:
    known = ids(ready)
    paths = [
        "/oggi", "/voci", f"/voci/{known['incontro']}", f"/voci/{known['libro']}/modifica", "/voci/nonesiste",
        "/collezioni", "/modelli", "/modelli/nuovo", "/modelli/libro", "/modelli/nonesiste", "/scuole", "/organon",
        "/benvenuto/consenso", "/benvenuto/accesso", "/benvenuto/copie", "/benvenuto/diario", "/scrivi/nonesiste",
    ]
    paths += [f"/scrivi/{slug}" for slug in ("sera", "aree", "mattina", "libro", "serie", "incontro", "persona", "desiderio")]
    paths += [f"/organon/{part}" for part in ("parresia", "daimon", "mnemosyne", "nuvole", "info")]
    for path in paths:
        ctx = AppContext(ready)
        ctx.wide = wide
        route = parse_route(path)
        assert isinstance(SCREENS[route.screen](ctx, route), ft.Control), path


def test_screens_cover_every_route_kind() -> None:
    assert ONBOARDING_SCREENS <= set(SCREENS)
    assert {"oggi", "voci", "voce", "scrivi", "modifica", "collezioni", "modelli", "modello", "scuole", "organon", "parte"} <= set(SCREENS)


def test_missing_entry_and_template_say_so_gently(ready: Path) -> None:
    ctx = AppContext(ready)
    shown = texts(SCREENS["voce"](ctx, parse_route("/voci/nonesiste")))
    assert any("non esiste più" in text for text in shown)
    shown = texts(SCREENS["scrivi"](ctx, parse_route("/scrivi/nonesiste")))
    assert any("Scuole" in text for text in shown)


# * — the shell —


def test_first_run_consent_then_diary_then_today(folder: Path) -> None:
    page = FakePage()
    shell = Shell(page, folder)
    shell.start("/")
    assert shell.current.screen == "consenso"
    assert page.navigation_bar is None
    click(button(shell.body.content, "Non ora"))
    assert shell.current.screen == "consenso"  # nothing saved, the page stays
    click(button(shell.body.content, "Ho capito, iniziamo"))
    assert shell.current.screen == "diario"
    click(button(shell.body.content, "Installa il diario"))
    assert shell.current.screen == "oggi"
    with Store.open(folder) as store:
        assert store.find_template("sera") is not None
    assert shell.rail is not None and shell.rail.selected_index == 0


def test_a_changed_notice_is_asked_again_without_losing_anything(ready: Path) -> None:
    settings = load_settings(ready)
    settings["privacy"]["notice_version"] = NOTICE_VERSION - 1
    save_settings(ready, settings)
    shell = Shell(FakePage(), ready)
    shell.start("/voci")
    assert shell.current.screen == "consenso"
    assert any("cambiata" in text for text in texts(shell.body.content))
    click(button(shell.body.content, "Ho capito, continuiamo"))
    assert shell.current.screen == "voci"  # the start route survives the consent


def test_sign_in_is_asked_when_the_account_requires_it(ready: Path, monkeypatch) -> None:
    monkeypatch.setattr(services, "login_required", lambda folder: True)
    shell = Shell(FakePage(), ready)
    shell.start("/")
    assert shell.current.screen == "accesso"


def test_navigation_history_and_back(ready: Path) -> None:
    known = ids(ready)
    page = FakePage()
    shell = Shell(page, ready)
    shell.start("/oggi")
    shell.navigate("/voci")
    shell.navigate(f"/voci/{known['incontro']}")
    assert shell.section_key == "voci" and shell.rail.selected_index == 1
    shell.back()
    assert shell.current.path == "/voci"
    shell.back()
    assert shell.current.path == "/oggi"
    shell.navigate("/organon/daimon")
    shell.on_nav(SimpleNamespace(control=SimpleNamespace(selected_index=3)))
    assert shell.current.path == "/modelli" and shell.history == []
    shell.navigate("/scuole")
    shell.on_key(SimpleNamespace(key="Escape"))
    assert shell.current.path == "/modelli"
    shell.on_route_change(SimpleNamespace(route="/collezioni"))
    assert shell.current.path == "/collezioni"


def test_android_back_leaves_only_from_a_top_section(ready: Path) -> None:
    page = FakePage(width=412)
    shell = Shell(page, ready)
    shell.start("/oggi")
    shell.navigate("/organon/info")
    answers = []

    async def confirm_pop(value: bool) -> None:
        answers.append(value)

    event = SimpleNamespace(control=SimpleNamespace(confirm_pop=confirm_pop))
    asyncio.run(shell.on_confirm_pop(event))
    assert answers == [False] and shell.current.path == "/oggi"
    asyncio.run(shell.on_confirm_pop(event))
    assert answers == [False, True]


def test_resize_switches_rail_and_bar_keeping_the_screen(ready: Path) -> None:
    page = FakePage(width=1280)
    shell = Shell(page, ready)
    shell.start("/scrivi/sera")
    body = shell.body.content
    assert shell.rail is not None and page.navigation_bar is None
    shell.on_resize(SimpleNamespace(width=412, height=915))
    assert shell.layout == "narrow" and shell.bar is not None and page.navigation_bar is shell.bar
    assert shell.body.content is body  # what was typed stays
    shell.on_resize(SimpleNamespace(width=1280, height=800))
    assert shell.rail is not None and page.navigation_bar is None


def test_writing_an_entry_checks_required_fields_then_saves(ready: Path) -> None:
    page = FakePage()
    shell = Shell(page, ready)
    shell.start("/scrivi/libro")
    form = shell.body.content
    click(button(form, "Salva"))
    assert shell.current.screen == "scrivi"
    errors = [item.value for item in walk(form) if isinstance(item, ft.Text) and item.visible and item.value == "questo blocco è obbligatorio"]
    assert errors
    title = next(item for item in walk(form) if isinstance(item, ft.TextField))
    title.value = "Il barone rampante"
    title.on_change(SimpleNamespace(control=title))
    snapshots_before = len(backups.list_snapshots(ready))
    click(button(form, "Salva"))
    assert shell.current.screen == "voce"
    with Store.open(ready) as store:
        saved = store.get_entry(shell.current.arg)
        assert saved.values[store.get_template("libro").title_key] == "Il barone rampante"
    assert len(backups.list_snapshots(ready)) == snapshots_before + 1  # the daily snapshot ran after the save
    assert "Voce salvata." in shell.ctx.toasts


def test_deleting_an_entry_asks_first(ready: Path) -> None:
    known = ids(ready)
    page = FakePage()
    shell = Shell(page, ready)
    shell.start("/voci")
    shell.navigate(f"/voci/{known['sera']}")
    click(button(shell.body.content, "Cancella"))
    dialog = page.dialogs[-1]
    assert dialog.title == "Cancellare questa voce?"
    click(button(dialog, "Cancella"))
    assert shell.current.path == "/voci"
    with Store.open(ready) as store:
        assert known["sera"] not in [entry.id for entry in store.list_entries()]


def test_the_shell_toasts_due_reminders(ready: Path, monkeypatch) -> None:
    sent = SimpleNamespace(sent=[SimpleNamespace(moment="sera", body="Com'è andata oggi?")])
    monkeypatch.setattr(services, "fire_reminders", lambda folder, now, notifier: sent)
    shell = Shell(FakePage(), ready)
    shell.start("/oggi")
    asyncio.run(shell.check_reminders())
    assert shell.ctx.toasts[-1] == "Com'è andata oggi?"


def test_installing_a_pack_from_scuole(folder: Path) -> None:
    record_consent(folder, True, NOTICE_VERSION)
    services.save_ui_settings(folder, diario_suggested=True)
    page = FakePage()
    shell = Shell(page, folder)
    shell.start("/scuole")
    first = button(shell.body.content, "Vedi cosa cambia")
    click(first)
    click(button(shell.body.content, "Installa"))
    with Store.open(folder) as store:
        assert len(store.list_templates()) > 0


def test_main_entry_point_uses_the_start_route(ready: Path, monkeypatch) -> None:
    from zibaldone.ui import app

    monkeypatch.setenv("ZIBALDONE_UI_START", "/collezioni")
    page = FakePage()
    started: List[Optional[str]] = []
    monkeypatch.setattr(app.Shell, "start", lambda self, path="": started.append(path))
    app.main(page)
    assert started == ["/collezioni"]


def test_the_shell_says_when_a_new_version_is_out(ready: Path, monkeypatch) -> None:
    from zibaldone.cloud.updates import Release
    from zibaldone.ui import app

    release = Release("9.9.9", "zibaldone-v9.9.9", "https://example.org/release", "https://example.org/ZibaldOne-9.9.9.apk")
    monkeypatch.setattr(app, "UPDATE_CHECK_DELAY_SECONDS", 0)
    monkeypatch.setattr(services, "check_updates", lambda folder: release)
    page = FakePage()
    shell = Shell(page, ready)
    shell.start("/oggi")
    asyncio.run(shell.update_check())
    assert shell.ctx.toasts[-1] == "È uscita ZibaldOne 9.9.9."
    assert page.dialogs[-1].action == "Scarica"


def test_the_shell_stays_quiet_when_up_to_date(ready: Path, monkeypatch) -> None:
    from zibaldone.ui import app

    monkeypatch.setattr(app, "UPDATE_CHECK_DELAY_SECONDS", 0)
    monkeypatch.setattr(services, "check_updates", lambda folder: None)
    shell = Shell(FakePage(), ready)
    shell.start("/oggi")
    before = list(shell.ctx.toasts)
    asyncio.run(shell.update_check())
    assert shell.ctx.toasts == before


def test_the_info_screen_checks_for_updates_on_request(ready: Path, monkeypatch) -> None:
    from zibaldone.cloud.updates import Release

    asked: List[bool] = []
    monkeypatch.setattr(services, "check_updates_now", lambda folder: asked.append(True) or Release("9.9.9", "zibaldone-v9.9.9", "https://example.org/r"))
    shell = Shell(FakePage(), ready)
    shell.start("/organon/info")
    screen = shell.body.content
    assert "Controlla da sola una volta al giorno" in texts(screen)
    click(button(screen, "Controlla adesso"))
    assert asked == [True]
    assert any(text.startswith("È uscita ZibaldOne 9.9.9") for text in texts(shell.body.content))
    switch = next(item for item in walk(screen) if isinstance(item, ft.Switch) and item.label == "Controlla da sola una volta al giorno")
    switch.value = False
    switch.on_change(SimpleNamespace(control=switch))
    assert services.update_check_enabled(ready) is False
