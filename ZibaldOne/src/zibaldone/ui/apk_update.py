"""The new APK, from the app (KAN-12, KAN-13): Android's download manager puts it in Download,
then the system installer opens and asks one confirmation. Nothing is installed silently.

Android only, through `pyjnius`. Elsewhere, or when something fails, the caller opens the link in the browser.
"""

import asyncio
import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)

APK_TYPE = "application/vnd.android.package-archive"
POLL_SECONDS = 1.0
# DownloadManager.STATUS_*
PENDING, RUNNING, PAUSED, SUCCESSFUL, FAILED = 1, 2, 4, 8, 16


@dataclass(frozen=True)
class Progress:
    status: int
    done: int = 0
    total: int = 0

    @property
    def finished(self) -> bool:
        return self.status in (SUCCESSFUL, FAILED)


def file_name(version: str) -> str:
    """`ZibaldOne-0.3.3-android.apk`: only safe characters reach the Download folder."""
    return f"ZibaldOne-{re.sub(r'[^0-9A-Za-z.]', '', version) or 'nuova'}-android.apk"


class AndroidDownloads:
    """DownloadManager and the installer intent, through pyjnius."""

    def __init__(self) -> None:
        from jnius import autoclass, cast  # only in the Android build

        self.autoclass = autoclass
        host = os.environ.get("MAIN_ACTIVITY_HOST_CLASS_NAME", "")
        if not host:
            raise RuntimeError("Flet activity not found")
        self.activity = autoclass(host).mActivity
        self.manager_class = autoclass("android.app.DownloadManager")
        context = autoclass("android.content.Context")
        self.manager = cast("android.app.DownloadManager", self.activity.getSystemService(context.DOWNLOAD_SERVICE))  # getSystemService answers Object

    def start(self, url: str, name: str) -> int:
        uri = self.autoclass("android.net.Uri").parse(url)
        environment = self.autoclass("android.os.Environment")
        request = self.autoclass("android.app.DownloadManager$Request")(uri)
        request.setTitle(name)
        request.setDescription("Aggiornamento di ZibaldOne")
        request.setMimeType(APK_TYPE)
        request.setNotificationVisibility(self.autoclass("android.app.DownloadManager$Request").VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
        request.setDestinationInExternalPublicDir(environment.DIRECTORY_DOWNLOADS, name)
        return int(self.manager.enqueue(request))

    def progress(self, download_id: int) -> Progress:
        query = self.autoclass("android.app.DownloadManager$Query")()
        query.setFilterById([download_id])
        cursor = self.manager.query(query)
        try:
            if cursor is None or not cursor.moveToFirst():
                return Progress(FAILED)
            column = self.manager_class

            def value(name: str) -> int:
                return int(cursor.getLong(cursor.getColumnIndex(name)))

            return Progress(value(column.COLUMN_STATUS), value(column.COLUMN_BYTES_DOWNLOADED_SO_FAR), value(column.COLUMN_TOTAL_SIZE_BYTES))
        finally:
            if cursor is not None:
                cursor.close()

    def install(self, download_id: int) -> None:
        """The system installer, on the file the download manager wrote (a content:// link it shares)."""
        uri = self.manager.getUriForDownloadedFile(download_id)
        if uri is None:
            raise RuntimeError("downloaded file not found")
        intent_class = self.autoclass("android.content.Intent")
        intent = intent_class(intent_class.ACTION_VIEW)
        intent.setDataAndType(uri, APK_TYPE)
        intent.addFlags(intent_class.FLAG_GRANT_READ_URI_PERMISSION | intent_class.FLAG_ACTIVITY_NEW_TASK)
        self.activity.startActivity(intent)


def downloads() -> Optional[Any]:
    """The Android downloads, or None where they are not available (desktop, web, pyjnius missing)."""
    from zibaldone.ui import services

    if not services.running_on_android():
        return None
    try:
        return AndroidDownloads()
    except Exception:  # pyjnius missing, or Android refused
        logger.info("android downloads not available", exc_info=True)
        return None


def fetch(ctx: Any, release: Any) -> None:
    """«Scarica»: on Android the APK goes to Download and the installer opens; elsewhere the release page.

    The Java calls stay on the app's event loop (one thread, attached to Java once), and each is quick.
    """
    from zibaldone.ui import services

    android = services.running_on_android()
    link = release.apk_url if android and release.apk_url else release.page_url
    if ctx.memory.get("apk_download"):
        ctx.toast("Sto già scaricando l'aggiornamento: lo trovi anche nelle notifiche.")
        return
    manager = downloads() if android and release.apk_url and ctx.page is not None else None
    if manager is None:
        ctx.open_url(link)
        return
    name = file_name(release.version)

    async def task() -> None:
        try:
            download_id = manager.start(release.apk_url, name)
            ctx.toast(f"Scarico ZibaldOne {release.version} nella cartella Download…")
            ctx.update()
            progress = manager.progress(download_id)
            while not progress.finished:
                await asyncio.sleep(POLL_SECONDS)
                progress = manager.progress(download_id)
            if progress.status != SUCCESSFUL:
                raise RuntimeError("download failed")
            ctx.toast(f"{name} è in Download. Si apre l'installazione: conferma per aggiornare.")
            ctx.update()
            manager.install(download_id)
        except Exception:
            logger.info("apk download failed", exc_info=True)
            ctx.toast("Non riesco a scaricare l'aggiornamento dall'app: lo apro nel browser.", error=True)
            ctx.open_url(link)
            ctx.update()
        finally:
            ctx.memory.pop("apk_download", None)

    ctx.memory["apk_download"] = True
    ctx.page.run_task(task)
