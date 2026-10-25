"""The screens and the shell, built headless with a stand-in page (needs flet, no window)."""

import asyncio
import dataclasses
from datetime import date
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
from zibaldone.ui import viewmodels as vm  # noqa: E402
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
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(coroutine)
        else:  # started from inside a background job (the daily backup after an import): tested on its own
            coroutine.close()


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
        "/grafo", f"/grafo/{known['persona']}", "/grafo/nonesiste", "/theoria",
        "/aree", "/aree/salute", "/aree/svago", "/scrivi/checkin_area/salute", "/scrivi/riflessione/lavoro",
        f"/persone/{known['persona']}", f"/persone/{known['libro']}", "/persone/nonesiste",
        "/albero", "/rete", "/rete/famiglia", "/finanze", "/finanze/2026-09", "/abitudini", "/viste", "/viste/nonesiste",
    ]
    paths += [f"/scrivi/{slug}" for slug in ("sera", "aree", "mattina", "libro", "serie", "incontro", "persona", "desiderio")]
    paths += [f"/organon/{part}" for part in ("parresia", "daimon", "mnemosyne", "nuvole", "velo", "home", "info")]
    for path in paths:
        ctx = AppContext(ready)
        ctx.wide = wide
        route = parse_route(path)
        assert isinstance(SCREENS[route.screen](ctx, route), ft.Control), path


def test_screens_cover_every_route_kind() -> None:
    assert ONBOARDING_SCREENS <= set(SCREENS)
    assert {"oggi", "voci", "voce", "scrivi", "modifica", "collezioni", "modelli", "modello", "scuole", "grafo", "theoria", "finanze", "abitudini", "viste", "vista", "aree", "area", "persona", "albero", "rete", "organon", "parte"} <= set(SCREENS)


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
    click(button(shell.body.content, "Inizia con i pacchetti di base"))
    assert shell.current.screen == "oggi"
    with Store.open(folder) as store:
        assert store.find_template("sera") is not None
        assert store.find_template("checkin_area") is not None  # 0.2.0: the areas pack comes along
        assert all(store.find_template(slug) is not None for slug in ("persona", "libro", "rituale", "vista"))  # one tap installs the base packs
        assert store.find_template("conto") is None  # Finanze stays on request
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


def test_sign_in_can_be_skipped_and_explains_itself(ready: Path, monkeypatch) -> None:
    monkeypatch.setattr(services, "login_required", lambda folder: not load_settings(folder).get("login_skipped"))
    shell = Shell(FakePage(), ready)
    shell.start("/")
    assert shell.current.screen == "accesso"
    shown = texts(shell.body.content)
    assert "Google vede solo la tua email e il tuo nome." in shown and "Senza account tutto resta su questo dispositivo. Puoi entrare più tardi dalle Nuvole, in Impostazioni." in shown
    assert not any("consigliamo" in text.lower() for text in shown)
    button(shell.body.content, "Entra con Google")
    click(button(shell.body.content, "Continua senza account"))
    assert shell.current.screen == "oggi" and load_settings(ready).get("login_skipped") is True


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
    assert shell.current.path == "/modelli" and shell.history[-1] == "/organon/daimon"  # the section left is kept: back returns to it
    shell.navigate("/scuole")
    shell.on_key(SimpleNamespace(key="Escape"))
    assert shell.current.path == "/modelli"
    shell.on_route_change(SimpleNamespace(route="/collezioni"))
    assert shell.current.path == "/collezioni"


def test_android_back_goes_to_the_previous_section_and_leaves_on_the_second_press(ready: Path) -> None:
    page = FakePage(width=412)
    shell = Shell(page, ready)
    shell.start("/oggi")
    shell.on_nav(SimpleNamespace(control=SimpleNamespace(selected_index=1)))  # Voci
    shell.on_nav(SimpleNamespace(control=SimpleNamespace(selected_index=3)))  # Modelli
    answers = []
    now = [100.0]
    shell.clock = lambda: now[0]

    async def confirm_pop(value: bool) -> None:
        answers.append(value)

    event = SimpleNamespace(control=SimpleNamespace(confirm_pop=confirm_pop))
    asyncio.run(shell.on_confirm_pop(event))
    assert answers == [False] and shell.current.path == "/voci"
    asyncio.run(shell.on_confirm_pop(event))
    assert answers == [False, False] and shell.current.path == "/oggi"
    asyncio.run(shell.on_confirm_pop(event))  # nothing left: the first press only asks
    assert answers == [False, False, False] and "Premi ancora indietro per uscire." in shell.ctx.toasts
    now[0] += 1.0
    asyncio.run(shell.on_confirm_pop(event))  # the second one, soon after, leaves
    assert answers[-1] is True
    answers.clear()
    now[0] += 30.0
    asyncio.run(shell.on_confirm_pop(event))  # too late: asks again
    assert answers == [False]


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


def test_an_entry_page_lists_who_cites_it(ready: Path) -> None:
    with Store.open(ready) as store:
        giulia = next(entry for entry in store.list_entries(template="persona"))
    shell = Shell(FakePage(), ready)
    shell.start(f"/voci/{giulia.id}")
    shown = texts(shell.body.content)
    assert "Citata da (1)" in shown and "Cena" in shown


def test_the_graph_opens_an_entry_on_tap(ready: Path) -> None:
    known = ids(ready)
    shell = Shell(FakePage(), ready)
    shell.start("/voci")
    click(button(shell.body.content, "Grafo"))
    assert shell.current.path == "/grafo"
    screen = next(item for item in walk(shell.body.content) if isinstance(item, ft.GestureDetector))
    canvas = screen.content
    assert any(isinstance(shape, ft.canvas.Circle) for shape in canvas.shapes)
    assert "Le più collegate" in texts(shell.body.content)
    graph_screen = screen.on_tap_down.__self__
    target = next(node for node in graph_screen.drawing.nodes if node.id == known["persona"])
    screen.on_tap_down(SimpleNamespace(local_position=SimpleNamespace(x=target.x, y=target.y)))
    assert shell.current.path == f"/voci/{known['persona']}"
    click(button(shell.body.content, "Nel grafo"))
    assert shell.current.path == f"/grafo/{known['persona']}"
    assert any(text.startswith("intorno a «Giulia»") for text in texts(shell.body.content))
    graph_screen = next(item for item in walk(shell.body.content) if isinstance(item, ft.GestureDetector)).on_tap_down.__self__
    graph_screen.resized(SimpleNamespace(width=500, height=300))
    assert graph_screen.drawing.width == 500


def test_statistics_and_the_weekly_review_from_oggi(ready: Path) -> None:
    page = FakePage()
    shell = Shell(page, ready)
    shell.start("/oggi")
    click(button(shell.body.content, "Statistiche"))
    assert shell.current.path == "/theoria"
    shown = texts(shell.body.content)
    assert "Scrittura" in shown and any(text.startswith("settimana ") for text in shown)
    click(button(shell.body.content, "Mese"))
    from zibaldone.core.stats import month_of

    assert button(shell.body.content, "Revisione del mese") and month_of(shell.ctx.now().date()).label in texts(shell.body.content)
    click(button(shell.body.content, "Settimana"))
    click(button(shell.body.content, "Revisione della settimana"))
    assert shell.current.screen == "modifica"
    assert "Revisione preparata con i dati del periodo: rileggila e completala." in shell.ctx.toasts
    with Store.open(ready) as store:
        assert len(store.list_entries(template="settimana")) == 1


def test_trying_the_anonymizer_from_organon(ready: Path) -> None:
    shell = Shell(FakePage(), ready)
    shell.start("/organon/velo")
    screen = shell.body.content
    click(button(screen, "Prova"))
    assert "Scrivi o incolla un testo, poi tocca Prova." in texts(shell.body.content)
    field = next(item for item in walk(screen) if isinstance(item, ft.TextField))
    field.value = "Cena con Giulia, chiamala al 333 123 4567."
    click(button(screen, "Prova"))
    shown = texts(shell.body.content)
    assert any("[PERSONA_1]" in text and "Giulia" not in text for text in shown)
    assert any(text.startswith("Sostituzioni (2)") for text in shown)
    click(button(screen, "Usa l'ultima voce"))
    assert field.value


# * — 0.2.0: the 8 areas —


def find(control: Any, kind: type, **attributes: Any) -> Any:
    for item in walk(control):
        if isinstance(item, kind) and all(getattr(item, name, None) == value for name, value in attributes.items()):
            return item
    raise LookupError(f"no {kind.__name__} with {attributes}")


def with_areas_pack(folder: Path) -> None:
    with Store.open(folder) as store:
        apply_install(plan_install(find_builtin_pack("aree"), store), store)


def test_the_areas_from_oggi_with_to_dos_and_coming_soon(ready: Path) -> None:
    with_areas_pack(ready)
    with Store.open(ready) as store:
        store.add_entry("aree", {"salute": 7, "lavoro": 4})
        store.add_entry("obiettivo", {"titolo": "Correre 10 km", "passi": ["5 km"]}, area="salute")
    shell = Shell(FakePage(), ready)
    shell.start("/oggi")
    click(button(shell.body.content, "Aree"))
    assert shell.current.path == "/aree"
    shown = texts(shell.body.content)
    assert "Le otto aree" in shown and "Diggy" in shown and "7/10" in shown
    assert "IN ARRIVO PER TUTTE LE AREE" in shown and "Maieutica" in shown and "In arrivo · dopo la 1.0" in shown
    card = next(item for item in walk(shell.body.content) if getattr(item, "on_click", None) and "Salute" in texts(item) and "Diggy" in texts(item))
    click(card)
    assert shell.current.path == "/aree/salute" and shell.section_key == "oggi"
    shown = texts(shell.body.content)
    assert "Correre 10 km" in shown and "5 km" in shown and "Da fare (1)" in shown
    field = find(shell.body.content, ft.TextField, hint_text="Che cosa c'è da fare?")
    field.value = "prenotare il dentista"
    click(button(shell.body.content, "Aggiungi"))
    assert "Aggiunto alle cose da fare." in shell.ctx.toasts
    assert "Da fare (2)" in texts(shell.body.content)
    box = next(item for item in walk(shell.body.content) if isinstance(item, ft.Checkbox))
    box.on_change(SimpleNamespace(control=SimpleNamespace(value=True)))
    assert "Fatto: 5 km." in shell.ctx.toasts and "Da fare (1)" in texts(shell.body.content)
    with Store.open(ready) as store:
        goal = store.list_entries(template="obiettivo")[0]
        assert goal.values["passi"] == [{"text": "5 km", "done": True}]


def test_an_area_check_in_starts_in_its_area(ready: Path) -> None:
    with_areas_pack(ready)
    shell = Shell(FakePage(), ready)
    shell.start("/aree/lavoro")
    click(button(shell.body.content, "Check-in"))
    assert shell.current.path == "/scrivi/checkin_area/lavoro"
    menu = find(shell.body.content, ft.Dropdown, label="Area della vita")
    assert menu.value == "lavoro"
    click(button(shell.body.content, "Salva"))
    assert shell.current.screen == "voce"
    with Store.open(ready) as store:
        assert store.get_entry(shell.current.arg).area == "lavoro"
    assert any(text == "Lavoro" for text in texts(shell.body.content))  # the area chip on the entry


def test_a_check_in_without_area_asks_for_one(ready: Path) -> None:
    with_areas_pack(ready)
    shell = Shell(FakePage(), ready)
    shell.start("/scrivi/checkin_area")
    form = shell.body.content
    click(button(form, "Salva"))
    assert shell.current.screen == "scrivi"
    assert any(isinstance(item, ft.Text) and item.visible and item.value == "scegli l'area di questo check-in" for item in walk(form))
    menu = find(form, ft.Dropdown, label="Area della vita")
    menu.value = "studio"
    menu.on_select(SimpleNamespace(control=menu))
    click(button(form, "Salva"))
    assert shell.current.screen == "voce"


def test_an_area_page_offers_the_missing_pack(ready: Path) -> None:
    shell = Shell(FakePage(), ready)
    shell.start("/aree/finanze")
    assert any("Liceo · Aree" in text for text in texts(shell.body.content))
    click(button(shell.body.content, "Installa «Liceo · Aree»"))
    assert "Liceo · Aree installato: 3 modelli." in shell.ctx.toasts
    assert button(shell.body.content, "Check-in")


def test_entries_by_area_and_the_area_of_a_template(ready: Path) -> None:
    known = ids(ready)
    shell = Shell(FakePage(), ready)
    shell.start(f"/voci/{known['libro']}")
    assert "Svago" in texts(shell.body.content)  # Libro belongs to svago
    shell.navigate("/voci")
    menu = find(shell.body.content, ft.Dropdown, label="Area")
    menu.value = "svago"
    menu.on_select(SimpleNamespace(control=menu))
    shown = texts(shell.body.content)
    assert "Ficciones" in shown and "Cena" not in shown and "1 voce" in shown
    shell.navigate("/modelli/libro")
    editor_menu = find(shell.body.content, ft.Dropdown, label="Area della vita delle sue voci")
    assert editor_menu.value == "svago"


# * — 0.2.1: people —


def test_a_person_from_the_area_page_with_contacts(ready: Path) -> None:
    with Store.open(ready) as store:
        giulia = next(entry for entry in store.list_entries(template="persona"))
        store.update_entry(giulia.id, {"telefono": "+39 333 1234567", "frequenza": "Ogni settimana", "ruoli": ["sorella"]})
    shell = Shell(FakePage(), ready)
    shell.start("/aree/famiglia")
    shown = texts(shell.body.content)
    assert "Persone (1)" in shown and "Giulia" in shown and "da sentire" not in shown
    row = next(item for item in walk(shell.body.content) if getattr(item, "on_click", None) and "Giulia" in texts(item) and "Persone (1)" not in texts(item))
    click(row)
    assert shell.current.path == f"/persone/{giulia.id}"
    shown = texts(shell.body.content)
    assert "Giulia" in shown and "sorella" in shown and "+39 333 1234567" in shown and "Cena" in shown
    assert "Famiglia" in shown and "Sociale (1)" in shown  # the dinner (Simposio) is in Sociale
    click(button(shell.body.content, "Chiamata"))
    assert "Segnato: Chiamata con Giulia." in shell.ctx.toasts
    shown = texts(shell.body.content)
    assert "Chiamata con Giulia" in shown and "Famiglia (1)" in shown
    shell.start(f"/voci/{giulia.id}")
    click(button(shell.body.content, "Tutto di Giulia"))
    assert shell.current.path == f"/persone/{giulia.id}"


# * — 0.2.2: family tree and network —


def test_family_tree_and_network_from_a_person(ready: Path) -> None:
    with Store.open(ready) as store:
        giulia = next(entry for entry in store.list_entries(template="persona"))
        anna = store.add_entry("persona", {"nome": "Anna", "ruoli": ["madre"]})
        store.update_entry(giulia.id, {"ruoli": ["sorella"], "genitori": [anna.id]})
    assert parse_route("/rete/Famiglia").arg == "famiglia" and parse_route("/rete/nonesiste").screen == "oggi"
    shell = Shell(FakePage(), ready)
    shell.start(f"/persone/{giulia.id}")
    shown = texts(shell.body.content)
    assert "Legami (1)" in shown and "Anna" in shown and "genitore" in shown
    click(button(shell.body.content, "Albero"))
    assert shell.current.path == "/albero"
    shown = texts(shell.body.content)
    assert shown.index("Genitori e zii") < shown.index("Anna") < shown.index("Tu, fratelli e cugini") < shown.index("Giulia")
    assert "sorella · genitori: Anna" in shown
    shell.start("/aree/famiglia")
    click(button(shell.body.content, "Rete"))
    assert shell.current.path == "/rete/famiglia"
    shown = texts(shell.body.content)
    assert "Rete · Famiglia" in shown and "2 persone, 1 legame" in shown
    with Store.open(ready) as store:
        view = vm.network_view(store, "", date(2026, 10, 17))
    assert {node.label for node in view.graph.nodes} == {"Anna", "Giulia"} and view.strongest[0].name == "Giulia"


def test_secrets_in_the_app_write_freely_and_open_with_the_pin(ready: Path, monkeypatch) -> None:
    from zibaldone.core import secrets
    from zibaldone.core.crypto import ScryptParams
    from zibaldone.storage import keys

    monkeypatch.setattr(keys, "DEFAULT_SCRYPT_PARAMS", ScryptParams(n=2**10))
    monkeypatch.setattr(keys, "PIN_SCRYPT_PARAMS", ScryptParams(n=2**10))
    passphrase = "cavallo batteria graffetta"
    with Store.open(ready) as store:
        apply_install(plan_install(find_builtin_pack("segreti"), store), store)
    keys.setup_keys(ready, passphrase)
    page = FakePage()
    shell = Shell(page, ready)
    shell.start("/scrivi/diario_segreto")
    form = shell.body.content
    field = next(item for item in walk(form) if isinstance(item, ft.TextField) and item.multiline)
    field.value = "caro diario, oggi"
    field.on_change(SimpleNamespace(control=field))
    click(button(form, "Salva"))
    assert shell.current.screen == "voce", texts(form)
    entry_id = shell.current.arg
    shown = texts(shell.body.content)
    assert "caro diario, oggi" not in shown and "cifrato · protetto" in shown
    # the PIN, chosen in Mnemosyne
    shell.navigate("/organon/mnemosyne")
    click(button(shell.body.content, "Scegli il PIN"))
    dialog = page.dialogs[-1]
    fields = [item for item in walk(dialog) if isinstance(item, ft.TextField)]
    for item, value in zip(fields, (passphrase, "246810", "246810")):
        item.value = value
    click(button(dialog, "Scegli il PIN"))
    assert keys.has_pin(ready) and any("PIN scelto" in toast for toast in shell.ctx.toasts)
    # opening the entry asks the PIN, then shows the text
    shell.navigate(f"/voci/{entry_id}")
    click(button(shell.body.content, "Apri"))
    dialog = page.dialogs[-1]
    assert "Il PIN apre i segreti protetti di questo dispositivo." in texts(dialog)
    pin = next(item for item in walk(dialog) if isinstance(item, ft.TextField))
    pin.value = "000000"
    click(button(dialog, "Apri"))
    assert "PIN sbagliato: ancora 4 tentativi" in texts(dialog)
    pin.value = "246810"
    click(button(dialog, "Apri"))
    assert "caro diario, oggi" in texts(shell.body.content)
    # editing shows it while open; saving another block keeps the same sealed value
    click(button(shell.body.content, "Modifica"))
    form = shell.body.content
    assert any(isinstance(item, ft.TextField) and item.value == "caro diario, oggi" for item in walk(form))
    with Store.open(ready) as store:
        before = store.get_entry(entry_id).values["testo"]
    click(button(form, "Salva le modifiche"))
    with Store.open(ready) as store:
        assert store.get_entry(entry_id).values["testo"] == before
    shell.ctx.memory["vault"].lock()
    shell.navigate(f"/voci/{entry_id}")
    assert "caro diario, oggi" not in texts(shell.body.content)
    with Store.open(ready) as store:
        assert vm.entry_detail(store, entry_id, date(2026, 10, 17)).blocks[0].text == secrets.LOCKED_TEXT


def test_attaching_a_photo_and_a_document_to_the_evening(ready: Path, tmp_path: Path) -> None:
    photo, document = tmp_path / "mare.jpg", tmp_path / "biglietto.pdf"
    photo.write_bytes(b"\x89PNG il mare")
    document.write_bytes(b"%PDF il biglietto")
    shell = Shell(FakePage(), ready)
    shell.ctx.pick_files = lambda on_picked: on_picked([SimpleNamespace(name=path.name, path=str(path), bytes=None) for path in (photo, document)])
    shell.start("/scrivi/sera")
    form = shell.body.content
    click(button(form, "Aggiungi file"))
    assert "mare.jpg" in texts(form) and "biglietto.pdf" in texts(form)
    click(button(form, "Salva"))
    assert shell.current.screen == "voce"
    detail = shell.body.content
    thumbnail = next(item for item in walk(detail) if isinstance(item, ft.Container) and isinstance(item.content, ft.Image))
    assert thumbnail.content.src == b"\x89PNG il mare" and "biglietto.pdf" in texts(detail)
    click(thumbnail)
    click(button(detail, "Apri"))
    assert [path.name.rsplit(".", 1)[-1] for path in shell.ctx.opened] == ["jpg", "pdf"]
    assert all(path.read_bytes() in (photo.read_bytes(), document.read_bytes()) for path in shell.ctx.opened)


def test_half_stars_favorite_spoiler_and_dates_in_the_book(ready: Path) -> None:
    with Store.open(ready) as store:
        dune = store.add_entry(
            "libro",
            {"titolo": "Dune", "voto": 4.5, "preferito": True, "recensione_spoiler": "Il finale svela tutto", "stato": {"status": "completed", "total": 600, "started": "2026-09-01", "finished": "2026-10-03"}},
        )
    shell = Shell(FakePage(), ready)
    shell.start(f"/voci/{dune.id}")
    detail = shell.body.content
    shown = texts(detail)
    assert "contiene spoiler" in shown and "Il finale svela tutto" not in shown and "sì" in shown
    assert any(item.startswith("iniziato") and "1 settembre 2026" in item and "finito" in item and "3 ottobre 2026" in item for item in shown)
    assert any(isinstance(item, ft.Icon) and item.icon == ft.Icons.STAR_HALF for item in walk(detail))
    click(button(detail, "Mostra"))
    assert "Il finale svela tutto" in texts(detail)
    click(button(detail, "Nascondi"))
    assert "Il finale svela tutto" not in texts(detail)
    # the form: a star twice makes it half, a third tap clears it; the heart switches on
    click(button(detail, "Modifica"))
    form = shell.body.content
    star = next(item for item in walk(form) if isinstance(item, ft.IconButton) and item.tooltip == "3 su 5")
    click(star)
    click(star)
    assert "2,5 su 5" in texts(form)
    heart = next(item for item in walk(form) if isinstance(item, ft.IconButton) and item.tooltip == "Preferito")
    click(heart)
    assert "non è tra i preferiti" in texts(form)
    click(button(form, "Salva le modifiche"))
    with Store.open(ready) as store:
        saved = store.get_entry(dune.id).values
    assert saved["voto"] == 2.5 and "preferito" not in saved
    assert saved["stato"]["started"] == "2026-09-01" and saved["stato"]["finished"] == "2026-10-03"  # the dates survive a save from the form


def test_collections_show_favorites_wishes_time_and_import_from_a_file(ready: Path, tmp_path: Path) -> None:
    with Store.open(ready) as store:
        store.add_entry("libro", {"titolo": "Dune", "preferito": True})
        store.add_entry("libro", {"titolo": "Ubik", "stato": {"status": "wishlist"}})
        store.add_entry("videogioco", {"titolo": "Hades", "ore": 12.5})
    shell = Shell(FakePage(), ready)
    shell.start("/collezioni")
    shown = texts(shell.body.content)
    assert {"PREFERITI", "LISTA DEI DESIDERI", "TEMPO SPESO", "12,5 ore"} <= set(shown) and "Ubik · Biblioteca di Babele" in shown
    # import: pick the service, the file, see the count, confirm
    export = tmp_path / "goodreads_library_export.csv"
    export.write_text(
        "Title,Author,My Rating,Exclusive Shelf,Date Read\nLa strada,Cormac McCarthy,4,read,2024/05/12\nDune,Frank Herbert,0,read,\n", encoding="utf-8"
    )
    shell.ctx.pick_files = lambda on_picked, multiple=True: on_picked([SimpleNamespace(name=export.name, path=str(export), bytes=None)])
    click(button(shell.body.content, "Importa da un file"))
    dialog = shell.ctx.page.dialogs[-1]
    source = next(item for item in walk(dialog) if isinstance(item, ft.Container) and "Goodreads · libri" in texts(item) and item.on_click)
    click(source)
    dialog = shell.ctx.page.dialogs[-1]
    assert "Dal file di Goodreads: Da aggiungere: 1 libro. 1 già presenti, lasciati come sono." in texts(dialog)
    click(button(dialog, "Importa"))
    assert any("Aggiunti: 1 libro" in toast for toast in shell.ctx.toasts)
    with Store.open(ready) as store:
        assert sorted(entry.values["titolo"] for entry in store.list_entries(template="libro")) == ["Dune", "Ficciones", "La strada", "Ubik"]
    # a file that is not from the chosen service says so and writes nothing
    export.write_text("Name,Year\nHeat,1995\n", encoding="utf-8")
    click(button(shell.body.content, "Importa da un file"))
    click(next(item for item in walk(shell.ctx.page.dialogs[-1]) if isinstance(item, ft.Container) and "Goodreads · libri" in texts(item) and item.on_click))
    assert any("mancano le colonne Title" in toast for toast in shell.ctx.toasts)


def test_finance_screen_installs_asks_the_pin_and_adds_up(ready: Path, monkeypatch) -> None:
    from decimal import Decimal

    from zibaldone.core import finance as F
    from zibaldone.core import secrets as A
    from zibaldone.core.crypto import ScryptParams
    from zibaldone.storage import keys
    from zibaldone.ui.views.vault import vault_of

    monkeypatch.setattr(keys, "DEFAULT_SCRYPT_PARAMS", ScryptParams(n=2**10))
    shell = Shell(FakePage(), ready)
    shell.start("/finanze")
    click(button(shell.body.content, "Installa «Oikonomia · Finanze»"))
    assert "Gli importi si cifrano con la chiave dei backup, che non è ancora attiva." in texts(shell.body.content)
    new_keys = keys.setup_keys(ready, "cavallo batteria graffetta")
    with Store.open(ready) as store:
        store.add_entry("conto", {"nome": "Carta", "saldo": "1000"})
    shell.ctx.refresh()
    assert any("I conti sono chiusi" in text for text in texts(shell.body.content))
    vault_of(shell.ctx).unlock([A.everyday_key(new_keys.private_key)], shell.ctx.now())
    shell.ctx.refresh()
    assert "1.000,00 €" in texts(shell.body.content)
    click(button(shell.body.content, "Spesa"))
    dialog = shell.ctx.page.dialogs[-1]
    fields = [item for item in walk(dialog) if isinstance(item, ft.TextField)]
    fields[0].value, fields[1].value = "12,50", "Pizza"
    click(button(dialog, "Salva"))
    assert "Spesa registrata." in shell.ctx.toasts
    shown = texts(shell.body.content)
    assert "987,50 €" in shown and "Cibo" in shown and any("Spese 12,50 €" in text for text in shown)
    with Store.open(ready) as store:
        assert F.load(store, lambda value: vault_of(shell.ctx).reveal(value, shell.ctx.now())).movements[0].amount == Decimal("12.50")
    click(button(shell.body.content, "Richiudi"))
    assert any("I conti sono chiusi" in text for text in texts(shell.body.content))


def test_about_shows_the_mascot_drawings(ready: Path) -> None:
    shell = Shell(FakePage(), ready)
    shell.start("/organon/info")
    images = [item for item in walk(shell.body.content) if isinstance(item, ft.Image)]
    assert len(images) >= 8  # the eight drawn mascots; Zibby keeps its initial until it has a drawing


def test_backup_button_does_not_use_a_camera(ready: Path) -> None:
    shell = Shell(FakePage(), ready)
    shell.start("/organon/mnemosyne")
    create = button(shell.body.content, "Crea ora")
    assert create.icon == ft.Icons.BACKUP_OUTLINED


def test_template_editor_shows_the_area_mascot(ready: Path) -> None:
    shell = Shell(FakePage(), ready)
    shell.start("/modelli/nuovo")
    assert "Salute" not in texts(shell.body.content)  # no area yet, no badge
    menu = next(item for item in walk(shell.body.content) if isinstance(item, ft.Dropdown) and item.label == "Area della vita delle sue voci")
    menu.value = "salute"
    menu.on_select(SimpleNamespace(control=menu))
    assert "Salute" in texts(shell.body.content)
    from zibaldone.core.brand import mascot_for

    assert any(isinstance(item, ft.Container) and (item.tooltip or "").startswith(mascot_for("salute").name) for item in walk(shell.body.content))


def test_leaving_a_form_keeps_a_draft_that_can_be_resumed(ready: Path) -> None:
    from zibaldone.ui import drafts

    shell = Shell(FakePage(width=412), ready)
    shell.start("/oggi")
    shell.navigate("/scrivi/libro")
    field = next(item for item in walk(shell.body.content) if isinstance(item, ft.TextField))  # the first field is the title
    field.value = "Il nome della rosa"
    field.on_change(SimpleNamespace(control=field))
    shell.back()  # the phone's back button
    assert shell.current.path == "/oggi" and "Bozza salvata: la ritrovi in Voci." in shell.ctx.toasts
    assert list(drafts.load_all(ready)) == ["new:libro"]
    with Store.open(ready) as store:
        assert not [entry for entry in store.list_entries(template="libro") if entry.values.get("titolo") == "Il nome della rosa"]  # not an entry yet
    shell.navigate("/voci")
    assert "BOZZE" in texts(shell.body.content) and "Il nome della rosa" in texts(shell.body.content)
    shell.navigate("/scrivi/libro")  # resumed
    assert any(isinstance(item, ft.TextField) and item.value == "Il nome della rosa" for item in walk(shell.body.content))
    click(button(shell.body.content, "Salva"))
    assert drafts.load_all(ready) == {}  # saved: the draft is gone


def test_an_untouched_form_leaves_no_draft_and_a_draft_can_be_dropped(ready: Path) -> None:
    from zibaldone.ui import drafts

    shell = Shell(FakePage(), ready)
    shell.start("/oggi")
    shell.navigate("/scrivi/libro")
    shell.back()
    assert drafts.load_all(ready) == {}
    shell.navigate("/scrivi/libro")
    field = next(item for item in walk(shell.body.content) if isinstance(item, ft.TextField))  # the first field is the title
    field.value = "Bozza da buttare"
    field.on_change(SimpleNamespace(control=field))
    shell.back()
    shell.navigate("/scrivi/libro")
    click(button(shell.body.content, "Scarta la bozza"))
    assert drafts.load_all(ready) == {} and "Bozza scartata." in shell.ctx.toasts


def test_a_model_opens_a_new_entry_and_the_small_icons_edit_and_pin(ready: Path) -> None:
    from zibaldone.ui import services

    shell = Shell(FakePage(), ready)
    shell.ctx.memory["modelli_area"] = "svago"
    shell.start("/modelli")
    tile = next(item for item in walk(shell.body.content) if isinstance(item, ft.Container) and item.on_click and "Biblioteca di Babele" in texts(item))
    click(tile)
    assert shell.current.path == "/scrivi/libro"
    shell.back()
    edit = next(item for item in walk(shell.body.content) if isinstance(item, ft.IconButton) and item.tooltip == "Modifica il modello")
    click(edit)
    assert shell.current.screen == "modello"
    shell.back()
    click(next(item for item in walk(shell.body.content) if isinstance(item, ft.IconButton) and item.tooltip == "Metti in Oggi"))
    assert services.shortcuts(ready)[:1] != [] and "Aggiunto alle scorciatoie di Oggi." in shell.ctx.toasts
    shell.navigate("/oggi")
    chip = next(item for item in walk(shell.body.content) if isinstance(item, ft.Container) and (item.tooltip or "").startswith("Nuova voce:"))
    click(chip)
    assert shell.current.screen == "scrivi"


def test_each_collection_opens_its_own_page(ready: Path) -> None:
    with Store.open(ready) as store:
        store.add_entry("libro", {"titolo": "Dune"})
    shell = Shell(FakePage(width=412), ready)
    shell.start("/collezioni")
    assert "Dune" not in texts(shell.body.content)  # the items live on the child page
    card = next(item for item in walk(shell.body.content) if isinstance(item, ft.Container) and item.on_click and "Biblioteca di Babele" in texts(item))
    click(card)
    assert shell.current.path == "/collezioni/libro" and "Dune" in texts(shell.body.content) and shell.section_key == "collezioni"
    shell.back()
    assert shell.current.path == "/collezioni"
    shell.start("/collezioni/nonesiste")
    assert any("non esiste" in text for text in texts(shell.body.content))


def test_pack_list_does_not_show_pack_version_numbers(ready: Path) -> None:
    shell = Shell(FakePage(), ready)
    shell.start("/scuole")
    assert not any(text.startswith("versione ") for text in texts(shell.body.content))


def test_models_sit_in_area_pages_and_back_goes_to_the_general_one_first(ready: Path) -> None:
    shell = Shell(FakePage(), ready)
    shell.start("/modelli")
    assert shell.ctx.memory.get("modelli_area", "") == "" and "Biblioteca di Babele" not in texts(shell.body.content)
    click(next(item for item in walk(shell.body.content) if isinstance(item, ft.Container) and item.tooltip == "Svago"))
    assert "Biblioteca di Babele" in texts(shell.body.content) and "Conto" not in texts(shell.body.content)
    assert shell.can_go_back()
    shell.back()
    assert shell.ctx.memory["modelli_area"] == "" and shell.current.path == "/modelli"
    assert shell.ctx.back_hook is None


def test_a_long_press_and_drag_changes_the_area_page_in_a_loop(ready: Path) -> None:
    shell = Shell(FakePage(), ready)
    shell.start("/modelli")
    detector = next(item for item in walk(shell.body.content) if isinstance(item, ft.GestureDetector))
    detector.on_long_press_move_update(SimpleNamespace(offset_from_origin=SimpleNamespace(x=-120)))
    detector.on_long_press_end(None)
    assert shell.ctx.memory["modelli_area"] == "personale"
    detector = next(item for item in walk(shell.body.content) if isinstance(item, ft.GestureDetector))
    detector.on_long_press_move_update(SimpleNamespace(offset_from_origin=SimpleNamespace(x=120)))
    detector.on_long_press_end(None)
    assert shell.ctx.memory["modelli_area"] == ""
    detector = next(item for item in walk(shell.body.content) if isinstance(item, ft.GestureDetector))
    detector.on_long_press_move_update(SimpleNamespace(offset_from_origin=SimpleNamespace(x=120)))
    detector.on_long_press_end(None)
    assert shell.ctx.memory["modelli_area"] == "svago"
