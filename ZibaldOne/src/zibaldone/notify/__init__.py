"""Delivering reminders: system notifications on Android and desktop, or the terminal.

Every adapter follows `Notifier`: `send(title, body)` returns True only when the
platform accepted the notification. Optional packages are imported lazily, so
ZibaldOne works without them and falls back to printing in the terminal.
"""

import os
import sys
from typing import Mapping, Optional, Protocol, Sequence, runtime_checkable

ANDROID_ENV_VARS = ("ANDROID_ROOT", "ANDROID_DATA", "MAIN_ACTIVITY_HOST_CLASS_NAME")


@runtime_checkable
class Notifier(Protocol):
    name: str

    def send(self, title: str, body: str) -> bool:
        """Show a notification; True when it was handed to the system."""
        ...


class TerminalNotifier:
    """Prints the reminder: the fallback when no system notification is available."""

    name = "terminale"

    def send(self, title: str, body: str) -> bool:
        stream = sys.stdout
        if stream is None:  # pythonw on Windows has no terminal
            return False
        try:
            print(f"* {title} — {body}", file=stream, flush=True)
        except (OSError, UnicodeError):
            return False
        return True


class FallbackNotifier:
    """Tries each notifier in order until one succeeds; `last_used` names it."""

    def __init__(self, notifiers: Sequence[Notifier]) -> None:
        self.notifiers = list(notifiers)
        self.last_used: Optional[str] = None

    @property
    def name(self) -> str:
        return self.last_used or " o ".join(notifier.name for notifier in self.notifiers)

    def send(self, title: str, body: str) -> bool:
        for notifier in self.notifiers:
            if notifier.send(title, body):
                self.last_used = notifier.name
                return True
        return False


def running_on_android(environ: Optional[Mapping[str, str]] = None, platform: Optional[str] = None) -> bool:
    """True inside an Android app (Flet sets MAIN_ACTIVITY_HOST_CLASS_NAME) or Python built for Android."""
    environ = os.environ if environ is None else environ
    platform = sys.platform if platform is None else platform
    return platform == "android" or any(environ.get(name) for name in ANDROID_ENV_VARS)


def get_notifier() -> Notifier:
    """The best notifier for this device. Create it once and reuse it while the app runs."""
    if running_on_android():
        from zibaldone.notify.android import AndroidNotifier

        return AndroidNotifier()
    from zibaldone.notify.desktop import DesktopNotifierAdapter

    desktop = DesktopNotifierAdapter.create()
    if desktop is None:
        return TerminalNotifier()
    return FallbackNotifier([desktop, TerminalNotifier()])


__all__ = ["FallbackNotifier", "Notifier", "TerminalNotifier", "get_notifier", "running_on_android"]
