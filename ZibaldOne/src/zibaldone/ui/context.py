"""What every view receives: the data folder, the page and a few app-wide actions.

The shell (`zibaldone.ui.app`) fills in navigation; without a page (tests)
the actions do nothing, so views can be built and inspected headless.
"""

import asyncio
import logging
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional

import flet as ft

from zibaldone.storage.database import Store
from zibaldone.ui import services
from zibaldone.ui import theme as T
from zibaldone.ui import widgets as W

logger = logging.getLogger("zibaldone.ui")


class AppContext:
    def __init__(self, folder: Path, page: Optional[ft.Page] = None, clock: Optional[Callable[[], datetime]] = None) -> None:
        self.folder = folder
        self.page = page
        self.clock = clock or datetime.now
        self.wide = True
        self.memory: Dict[str, Any] = {}  # screen state kept while the app is open (filters …)
        self.toasts: List[str] = []  # what was shown, for tests
        self.opened: List[Path] = []  # files handed to the system, for tests
        self._navigate: Callable[[str, bool], None] = lambda path, replace: None
        self._back: Callable[[], None] = lambda: None
        self._refresh: Callable[[], None] = lambda: None
        self._advance: Callable[[], None] = lambda: None
        self._data_changed: Callable[[], None] = lambda: None
        self.back_hook: Optional[Callable[[], bool]] = None  # a screen with its own pages takes the back press first; True = used it
        self.leave_guard: Optional[Callable[[], None]] = None  # the open form keeps its draft when the screen changes

    # — time and data —

    def now(self) -> datetime:
        return self.clock()

    @contextmanager
    def store(self) -> Iterator[Store]:
        with services.open_store(self.folder) as store:
            yield store

    # — navigation (wired by the shell) —

    def go(self, path: str, replace: bool = False) -> None:
        self._navigate(path, replace)

    def back(self, *_: Any) -> None:
        self._back()

    def refresh(self, *_: Any) -> None:
        self._refresh()

    def advance(self, *_: Any) -> None:
        """Go to the next step of the first-run flow (consent, sign-in, diary, Oggi)."""
        self._advance()

    def data_changed(self) -> None:
        """Something was saved: the shell runs the daily backup in the background if due."""
        self._data_changed()

    # — page helpers —

    def update(self, *controls: ft.Control) -> None:
        if self.page is None:
            return
        try:
            if controls:
                for control in controls:
                    control.update()
            else:
                self.page.update()
        except Exception:  # a control not on the page any more: nothing to redraw
            logger.debug("update skipped", exc_info=True)

    def show_dialog(self, dialog: Any) -> None:
        if self.page is not None:
            self.page.show_dialog(dialog)

    def close_dialog(self, *_: Any) -> None:
        if self.page is not None:
            self.page.pop_dialog()

    def toast(self, message: str, error: bool = False, action: str = "", on_action: Optional[Callable[[], Any]] = None) -> None:
        self.toasts.append(message)
        if self.page is None:
            return
        bar = ft.SnackBar(
            content=ft.Text(message, color=T.TEXT, size=14),
            bgcolor=T.PANEL_HIGH,
            show_close_icon=error,
            close_icon_color=T.TEXT_DIM,
            duration=8000 if (error or action) else 4000,
            shape=ft.RoundedRectangleBorder(radius=T.RADIUS_SMALL, side=ft.BorderSide(1, T.ERROR if error else T.BORDER)),
        )
        if action and on_action is not None:
            bar.action = action
            bar.on_action = lambda _: on_action()
        self.page.show_dialog(bar)

    def confirm(
        self,
        title: str,
        message: str,
        confirm_label: str,
        on_confirm: Callable[[], Any],
        danger: bool = True,
        cancel_label: str = "Annulla",
        on_cancel: Optional[Callable[[], Any]] = None,
    ) -> None:
        def accept(_: Any) -> None:
            self.close_dialog()
            on_confirm()

        def decline(_: Any) -> None:
            self.close_dialog()
            if on_cancel is not None:
                on_cancel()

        button = W.danger_button(confirm_label, accept) if danger else W.primary_button(confirm_label, accept)
        dialog = ft.AlertDialog(
            modal=True,
            title=title,
            content=ft.Text(message, color=T.TEXT, size=14),
            actions=[W.text_button(cancel_label, decline, color=T.TEXT), button],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.show_dialog(dialog)

    def call_soon(self, action: Callable[[], Any]) -> None:
        """Run `action` on the UI loop; safe to call from a worker thread."""
        if self.page is None:
            action()
            return

        async def task() -> None:
            action()
            self.update()

        self.page.run_task(task)

    def open_url(self, url: str) -> None:
        """Open a page in the system browser; safe to call from a worker thread."""
        if self.page is None:
            return

        async def task() -> None:
            await ft.UrlLauncher().launch_url(url)

        self.page.run_task(task)

    def pick_files(self, on_picked: Callable[[List[Any]], Any], multiple: bool = True) -> None:
        """The system file picker (0.2.4); `on_picked` gets the chosen files (name, path or bytes)."""
        if self.page is None:
            return
        web = bool(getattr(self.page, "web", False))

        async def task() -> None:
            files = await ft.FilePicker().pick_files(allow_multiple=multiple, with_data=web)
            on_picked(list(files or []))
            self.update()

        self.page.run_task(task)

    def pick_folder(self, on_picked: Callable[[str], Any]) -> None:
        """The system folder picker; `on_picked` gets the path, or nothing happens when the user cancels."""
        if self.page is None:
            return

        async def task() -> None:
            path = await ft.FilePicker().get_directory_path()
            if path:
                on_picked(str(path))
            self.update()

        self.page.run_task(task)

    def ask_files_permission(self, on_result: Callable[[bool], Any]) -> None:
        """Ask Android for access to the phone's files (needed to make `ZibaldOne/Data` in the main storage); elsewhere there is nothing to ask. `on_result(granted)`."""
        if self.page is None or not services.running_on_android():
            on_result(True)
            return

        async def task() -> None:
            granted = False
            try:
                import flet_permission_handler as ph

                handler = self.memory.get("permission_handler")
                if handler is None:
                    handler = self.memory["permission_handler"] = ph.PermissionHandler()
                    self.page.services.append(handler)
                status = await handler.request(ph.Permission.MANAGE_EXTERNAL_STORAGE)
                granted = status == ph.PermissionStatus.GRANTED
            except Exception:  # library missing, or the system refused to ask
                logger.info("files permission failed", exc_info=True)
            on_result(granted)
            self.update()

        self.page.run_task(task)

    def open_file(self, path: Path) -> None:
        """Open an attached file with the system app; on a phone, through the share sheet."""
        self.opened.append(path)
        if self.page is None:
            return
        platform = getattr(self.page, "platform", None)

        async def task() -> None:
            try:
                if platform is not None and platform.is_mobile():
                    await ft.Share().share_files([ft.ShareFile.from_path(str(path))])
                else:
                    await ft.UrlLauncher().launch_url(path.as_uri())
            except Exception as error:  # no app for this kind of file
                logger.info("open file failed", exc_info=True)
                self.toast(f"Non riesco ad aprire il file: {error}", error=True)

        self.page.run_task(task)

    def run_blocking(
        self,
        work: Callable[[], Any],
        on_done: Callable[[Any], Any],
        on_error: Optional[Callable[[Exception], Any]] = None,
    ) -> None:
        """Run `work` in a thread (it must open its own Store), then call back on the UI side."""

        async def task() -> None:
            try:
                result = await asyncio.to_thread(work)
            except Exception as error:  # shown to the user, in Italian when the core wrote it
                logger.info("background work failed", exc_info=True)
                if on_error is not None:
                    on_error(error)
                else:
                    self.toast(str(error), error=True)
            else:
                on_done(result)
            self.update()

        if self.page is None:
            try:
                on_done(work())
            except Exception as error:
                if on_error is not None:
                    on_error(error)
            return
        self.page.run_task(task)
