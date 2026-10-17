"""Local notifications on Android through `android-notify` (optional, needs `pyjnius`).

DA VERIFICARE SUL TELEFONO: written from the android-notify documentation
(1.6x: `Notification(title=…, message=…, channel_name=…, channel_id=…).send()`,
`NotificationHandler.has_permission()` / `asks_permission()`), not tried on a device.
- Android 13+ needs the POST_NOTIFICATIONS permission, declared in the Flet build:
  `[tool.flet.android.permission] "android.permission.POST_NOTIFICATIONS" = true`
  and asked at runtime (`request_permission()`, best from a button the user taps).
- This sends notifications while the app is running. With the app closed Android
  needs native scheduling (AlarmManager / WorkManager): not covered here.
"""

from typing import Any, Callable, Optional

CHANNEL_ID = "zibaldone_promemoria"
CHANNEL_NAME = "Promemoria"


def _library() -> Optional[Any]:
    try:
        import android_notify
    except Exception:  # noqa: BLE001 - ImportError, or jnius failing outside Android
        return None
    return android_notify


class AndroidNotifier:
    name = "notifiche Android"

    def available(self) -> bool:
        return _library() is not None

    def has_permission(self) -> bool:
        library = _library()
        if library is None:
            return False
        try:
            return bool(library.NotificationHandler.has_permission())
        except Exception:  # noqa: BLE001
            return False

    def request_permission(self, callback: Optional[Callable[[bool], None]] = None) -> bool:
        """Show Android's permission dialog; `callback(granted)` runs when the user answers.

        Returns False when the request could not even be made.
        """
        library = _library()
        if library is None:
            return False
        try:
            library.NotificationHandler.asks_permission(callback=callback)
        except Exception:  # noqa: BLE001
            return False
        return True

    def send(self, title: str, body: str) -> bool:
        library = _library()
        if library is None:
            return False
        try:
            if not library.NotificationHandler.has_permission():
                # Not granted (yet): ask, and report this reminder as not delivered.
                library.NotificationHandler.asks_permission()
                return False
            notification = library.Notification(title=title, message=body, channel_name=CHANNEL_NAME, channel_id=CHANNEL_ID)
            notification.send()
        except Exception:  # noqa: BLE001 - a notification must never crash the app
            return False
        return True
