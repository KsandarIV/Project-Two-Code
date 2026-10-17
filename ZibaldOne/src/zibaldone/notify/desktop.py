"""System notifications on Windows, macOS and Linux through `desktop-notifier` >= 6.1 (optional).

Uses its synchronous API. From an asyncio event loop (a Flet `async` handler),
call `send` in a worker thread, e.g. `await asyncio.to_thread(notifier.send, title, body)`:
the sync API runs its own loop and cannot run inside another one.
"""

import logging
from typing import Any, Optional

APP_NAME = "ZibaldOne"
LIBRARY_LOGGER = "desktop_notifier"


class DesktopNotifierAdapter:
    name = "notifiche di sistema"

    def __init__(self, backend: Any) -> None:
        self.backend = backend

    @classmethod
    def create(cls) -> Optional["DesktopNotifierAdapter"]:
        """None when `desktop-notifier` is not installed or this system cannot use it."""
        try:
            from desktop_notifier import DesktopNotifierSync
        except ImportError:
            return None
        # The library logs failures with a traceback; we report them as False instead.
        logging.getLogger(LIBRARY_LOGGER).addHandler(logging.NullHandler())
        try:
            return cls(DesktopNotifierSync(app_name=APP_NAME))
        except Exception:  # noqa: BLE001 - any backend error means "not available here"
            return None

    def send(self, title: str, body: str) -> bool:
        # desktop-notifier never raises when delivery fails: `on_dispatched` (6.1+) runs only on success.
        dispatched: list[bool] = []
        try:
            self.backend.send(title=title, message=body, on_dispatched=lambda: dispatched.append(True))
        except Exception:  # noqa: BLE001 - a notification must never crash the app
            return False
        return bool(dispatched)
