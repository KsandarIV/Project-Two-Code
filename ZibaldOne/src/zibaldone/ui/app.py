"""The ZibaldOne window: theme, adaptive navigation, first-run flow and the Daimon.

Entry points:
- `main(page)`: what Flet calls (also what `flet build` packages);
- `run(web=False, port=0, route=None)`: start the app from Python;
- `python -m zibaldone.ui [--web] [--port N] [--route /voci]`.

Layout: below `theme.WIDE_MIN_WIDTH` a bottom NavigationBar (phone), above it
a NavigationRail on the left (desktop). The layout switches on resize while
the current screen, and anything typed in it, stays.
"""

import asyncio
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional

import flet as ft

from zibaldone.core.brand import APP_NAME, mascot_for
from zibaldone.core.privacy import NOTICE_VERSION
from zibaldone.storage.database import StoreError
from zibaldone.storage.settings import SettingsError, has_consent
from zibaldone.ui import services
from zibaldone.ui import theme as T
from zibaldone.ui import widgets as W
from zibaldone.ui.context import AppContext
from zibaldone.ui.navigation import HOME, SECTIONS, START_ROUTE_ENV, Route, layout_for, parse_route, section, section_index
from zibaldone.ui.views import ONBOARDING_SCREENS, SCREENS
from zibaldone.ui.views.common import error_screen

logger = logging.getLogger("zibaldone.ui")

REMINDER_FIRST_CHECK_SECONDS = 60
UPDATE_CHECK_DELAY_SECONDS = 5
REMINDER_INTERVAL_SECONDS = 300
EXIT_WINDOW_SECONDS = 2.0  # the second Android back within this leaves the app
HISTORY_KEEP = 50


class Shell:
    def __init__(self, page: ft.Page, folder: Path) -> None:
        self.page = page
        self.folder = folder
        self.ctx = AppContext(folder, page)
        self.ctx._navigate = self.navigate
        self.ctx._back = self.back
        self.ctx._refresh = self.refresh
        self.ctx._advance = self.advance
        self.ctx._data_changed = self.schedule_backup
        self.backup_running = False
        self.migration_checked = False
        self.history: List[str] = []
        self.clock = time.monotonic
        self.exit_asked = float("-inf")
        self.current: Route = HOME
        self.section_key = "oggi"
        self.layout = layout_for(page.width)
        self.ctx.wide = self.layout == "wide"
        self.mounted: Optional[tuple] = None  # (layout, with_nav) currently on screen
        self.body = ft.Container(expand=True, bgcolor=T.BG)
        self.rail: Optional[ft.NavigationRail] = None
        self.bar: Optional[ft.NavigationBar] = None
        self.notifier = services.InAppNotifier()
        self.start_path = "/oggi"

    # — start —

    def start(self, start_path: str = "") -> None:
        page = self.page
        page.title = APP_NAME
        page.theme_mode = ft.ThemeMode.DARK
        theme = W.build_theme()
        page.theme = theme
        page.dark_theme = theme
        page.bgcolor = T.BG
        page.padding = 0
        page.spacing = 0
        page.locale_configuration = ft.LocaleConfiguration(
            supported_locales=[ft.Locale("it", "IT")], current_locale=ft.Locale("it", "IT")
        )
        page.on_resize = self.on_resize
        page.on_keyboard_event = self.on_key
        page.on_route_change = self.on_route_change
        try:
            page.window.min_width = 360
            page.window.min_height = 560
        except Exception:  # not a desktop window
            pass
        try:
            root = page.views[0]
            root.on_confirm_pop = self.on_confirm_pop
        except Exception:
            logger.debug("no root view for the back gesture", exc_info=True)
        self.start_path = start_path if start_path and start_path != "/" else "/oggi"
        self.advance()
        page.run_task(self.reminder_loop)
        page.run_task(self.update_check)

    def first_run_step(self) -> Optional[str]:
        """The onboarding page still to show, or None when the app can open."""
        if not has_consent(self.folder, NOTICE_VERSION):
            return "/benvenuto/consenso"
        if services.login_required(self.folder):
            return "/benvenuto/accesso"
        if services.destination_choice_pending(self.folder):
            return "/benvenuto/copie"
        if not self.migration_checked:  # before the first Store.open may migrate the database
            self.migration_checked = True
            warning = services.pre_migration_backup(self.folder)
            if warning:
                self.ctx.toast(warning, error=True)
        with services.open_store(self.folder) as store:
            installed = [template.slug for template in store.list_templates()]
        if services.diario_suggestion_pending(self.folder, installed):
            return "/benvenuto/diario"
        return None

    def advance(self) -> None:
        try:
            step = self.first_run_step()
        except (SettingsError, StoreError, OSError) as problem:
            self.body.content = error_screen(self.ctx, f"I dati non si leggono: {problem}")
            self.mount(False)
            return
        self.history.clear()
        if step is not None:
            self.show(parse_route(step))
            return
        target = parse_route(self.start_path)
        if target.screen in ONBOARDING_SCREENS:
            target = HOME
        self.start_path = "/oggi"
        self.show(target)

    # — navigation —

    def navigate(self, path: str, replace: bool = False) -> None:
        route = parse_route(path)
        if not replace and self.current.path != route.path:
            self.history.append(self.current.path)
        while self.history and self.history[-1] == route.path:
            self.history.pop()
        del self.history[:-HISTORY_KEEP]
        self.show(route)

    def back(self) -> None:
        if self.ctx.back_hook is not None and self.ctx.back_hook():
            return
        while self.history:
            path = self.history.pop()
            if path != self.current.path:
                self.show(parse_route(path))
                return
        if not self.current.is_top_level and self.current.screen not in ONBOARDING_SCREENS:
            self.show(parse_route(section(self.section_key).route))

    def refresh(self) -> None:
        self.show(self.current)

    def can_go_back(self) -> bool:
        return bool(self.history) or not self.current.is_top_level or self.ctx.back_hook is not None

    def show(self, route: Route) -> None:
        self.ctx.back_hook = None
        guard, self.ctx.leave_guard = self.ctx.leave_guard, None
        if guard is not None and route.path != self.current.path:
            guard()
        self.current = route
        if route.section:
            self.section_key = route.section
        builder = SCREENS.get(route.screen, SCREENS["oggi"])
        try:
            control = builder(self.ctx, route)
        except Exception as problem:  # never leave the user on a blank page
            logger.exception("screen %s failed", route.path)
            control = error_screen(self.ctx, f"{type(problem).__name__}: {problem}")
        self.body.content = control
        with_nav = route.screen not in ONBOARDING_SCREENS
        if self.mounted != (self.layout, with_nav):
            self.mount(with_nav)
        else:
            self.sync_selection()
            self.page.update()

    # — layout —

    def destinations_rail(self) -> List[ft.NavigationRailDestination]:
        return [
            ft.NavigationRailDestination(
                icon=W.icon_of(item.icon),
                selected_icon=W.icon_of(item.selected_icon),
                label=ft.Column(
                    [ft.Text(item.label, size=12), ft.Text(item.nickname, size=10, italic=True, color=T.TEXT_DIM)],
                    spacing=0,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            )
            for item in SECTIONS
        ]

    def destinations_bar(self) -> List[ft.NavigationBarDestination]:
        return [
            ft.NavigationBarDestination(icon=W.icon_of(item.icon), selected_icon=W.icon_of(item.selected_icon), label=item.label)
            for item in SECTIONS
        ]

    def mount(self, with_nav: bool) -> None:
        page = self.page
        page.navigation_bar = None
        self.rail = self.bar = None
        if not with_nav:
            page.controls = [ft.SafeArea(self.body, expand=True)]
        elif self.layout == "wide":
            zibby = mascot_for("app")
            self.rail = ft.NavigationRail(
                destinations=self.destinations_rail(),
                selected_index=section_index(self.section_key),
                label_type=ft.NavigationRailLabelType.ALL,
                min_width=96,
                group_alignment=-0.85,
                bgcolor=T.PANEL,
                indicator_color=W.fade(T.ACCENT, 0.18),
                leading=ft.Container(
                    ft.Column([W.mascot_avatar(zibby, 36), ft.Text(APP_NAME, size=11, weight=ft.FontWeight.W_600, color=T.TEXT)], spacing=6, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=ft.Padding.only(top=18, bottom=12),
                ),
                on_change=self.on_nav,
            )
            page.controls = [
                ft.SafeArea(
                    ft.Row([self.rail, ft.VerticalDivider(width=1, thickness=1, color=T.BORDER), self.body], expand=True, spacing=0),
                    expand=True,
                )
            ]
        else:
            self.bar = ft.NavigationBar(
                destinations=self.destinations_bar(),
                selected_index=section_index(self.section_key),
                bgcolor=T.PANEL,
                indicator_color=W.fade(T.ACCENT, 0.18),
                label_behavior=ft.NavigationBarLabelBehavior.ALWAYS_SHOW,
                on_change=self.on_nav,
                border=ft.Border.only(top=ft.BorderSide(1, T.BORDER)),
            )
            page.navigation_bar = self.bar
            page.controls = [ft.SafeArea(self.body, expand=True)]
        self.mounted = (self.layout, with_nav)
        page.update()

    def sync_selection(self) -> None:
        index = section_index(self.section_key)
        if self.rail is not None:
            self.rail.selected_index = index
        if self.bar is not None:
            self.bar.selected_index = index

    # — events —

    def on_nav(self, event: Any) -> None:
        index = event.control.selected_index or 0
        self.navigate(SECTIONS[index].route)  # the section left stays in the history: back returns to it

    def on_route_change(self, event: Any) -> None:
        """The address changed from outside (web: typed URL, reload, browser history)."""
        route = parse_route(getattr(event, "route", "") or "/")
        if route.path == self.current.path or self.current.screen in ONBOARDING_SCREENS:
            return
        if route.screen in ONBOARDING_SCREENS:
            return
        self.navigate(route.path)

    def on_resize(self, event: Any) -> None:
        width = getattr(event, "width", None) or self.page.width
        layout = layout_for(width)
        if layout == self.layout:
            return
        self.layout = layout
        self.ctx.wide = layout == "wide"
        if self.mounted is not None:
            self.mount(self.mounted[1])

    def dialog_open(self) -> bool:
        dialogs = getattr(getattr(self.page, "_dialogs", None), "controls", None) or []
        return any(getattr(dialog, "open", False) for dialog in dialogs)

    def on_key(self, event: Any) -> None:
        """Esc goes back on desktop (an open dialog closes by itself instead)."""
        if getattr(event, "key", "") == "Escape" and not self.dialog_open():
            self.back()

    async def on_confirm_pop(self, event: Any) -> None:
        """Android back: go back inside the app; with nothing left to go back to, the second press within two seconds leaves."""
        view = event.control
        if self.can_go_back():
            await view.confirm_pop(False)
            self.back()
            return
        now = self.clock()
        if now - self.exit_asked <= EXIT_WINDOW_SECONDS:
            await view.confirm_pop(True)
            return
        self.exit_asked = now
        self.ctx.toast("Premi ancora indietro per uscire.")
        await view.confirm_pop(False)

    # — Mnemosyne in the background —

    def schedule_backup(self) -> None:
        """After a save: the daily snapshot if it is due, then the copy outside. One at a time."""
        if self.backup_running:
            return
        self.backup_running = True

        async def task() -> None:
            try:
                warning = await asyncio.to_thread(services.auto_backup, self.folder)
            finally:
                self.backup_running = False
            if warning:
                self.ctx.toast(warning, error=True)

        self.page.run_task(task)

    # — is there a newer version? (0.1.1) —

    async def update_check(self) -> None:
        await asyncio.sleep(UPDATE_CHECK_DELAY_SECONDS)
        try:
            if not has_consent(self.folder, NOTICE_VERSION):
                return
            release = await asyncio.to_thread(services.check_updates, self.folder)
        except Exception:
            logger.debug("update check failed", exc_info=True)
            return
        if release is not None:
            url = release.apk_url if services.running_on_android() and release.apk_url else release.page_url
            self.ctx.toast(f"È uscita ZibaldOne {release.version}.", action="Scarica", on_action=lambda: self.ctx.open_url(url))
            self.ctx.update()

    # — the Daimon while the app is open —

    async def reminder_loop(self) -> None:
        await asyncio.sleep(REMINDER_FIRST_CHECK_SECONDS)
        while True:
            try:
                await self.check_reminders()
            except Exception:
                logger.debug("reminder check failed", exc_info=True)
            await asyncio.sleep(REMINDER_INTERVAL_SECONDS)

    async def check_reminders(self) -> None:
        try:
            ready = has_consent(self.folder, NOTICE_VERSION)
        except SettingsError:
            return
        if not ready or self.current.screen in ONBOARDING_SCREENS:
            return
        result = await asyncio.to_thread(services.fire_reminders, self.folder, datetime.now(), self.notifier)
        self.notifier.take()
        for reminder in getattr(result, "sent", ()) or ():
            moment = reminder.moment
            self.ctx.toast(f"{reminder.body}", action="Scrivi", on_action=lambda moment=moment: self.ctx.go(f"/scrivi/{moment}"))


def main(page: ft.Page) -> None:
    """Flet entry point."""
    folder = services.resolve_data_folder()
    start = os.environ.get(START_ROUTE_ENV) or page.route or "/oggi"
    Shell(page, folder).start(start)


def run(web: bool = False, port: int = 0, route: Optional[str] = None, assets_dir: Optional[str] = None) -> None:
    """Start the app: a desktop window, or the browser with `web=True`."""
    if route:
        os.environ[START_ROUTE_ENV] = route
    view = ft.AppView.WEB_BROWSER if web else ft.AppView.FLET_APP
    ft.run(main, name="", view=view, port=port, assets_dir=assets_dir or str(W.ASSETS_DIR), no_cdn=True)
