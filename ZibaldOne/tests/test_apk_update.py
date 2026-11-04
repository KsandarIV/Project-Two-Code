"""KAN-12, KAN-13: «Scarica» on Android downloads the APK into Download and opens the installer."""

import asyncio
from typing import Any, List

import pytest

from zibaldone.cloud.updates import Release
from zibaldone.ui import apk_update, services

RELEASE = Release("0.3.3", "zibaldone-v0.3.3", "https://github.com/x/releases/tag/zibaldone-v0.3.3", "https://github.com/x/ZibaldOne-0.3.3-android.apk")


class FakePage:
    def run_task(self, task: Any) -> None:
        asyncio.run(task())


class FakeContext:
    def __init__(self) -> None:
        self.page = FakePage()
        self.memory: dict = {}
        self.toasts: List[str] = []
        self.opened: List[str] = []

    def toast(self, message: str, error: bool = False) -> None:
        self.toasts.append(message)

    def open_url(self, url: str) -> None:
        self.opened.append(url)

    def update(self) -> None:
        pass


class FakeDownloads:
    def __init__(self, statuses: List[int]) -> None:
        self.statuses = statuses
        self.started: List[tuple] = []
        self.installed: List[int] = []

    def start(self, url: str, name: str) -> int:
        self.started.append((url, name))
        return 7

    def progress(self, download_id: int) -> apk_update.Progress:
        return apk_update.Progress(self.statuses.pop(0))

    def install(self, download_id: int) -> None:
        self.installed.append(download_id)


@pytest.fixture
def android(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(services, "running_on_android", lambda: True)
    monkeypatch.setattr(apk_update, "POLL_SECONDS", 0)


def test_file_name_keeps_only_safe_characters() -> None:
    assert apk_update.file_name("0.3.3.1") == "ZibaldOne-0.3.3.1-android.apk"
    assert apk_update.file_name("../x") == "ZibaldOne-..x-android.apk"


def test_on_the_pc_scarica_opens_the_release_page(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(services, "running_on_android", lambda: False)
    ctx = FakeContext()
    apk_update.fetch(ctx, RELEASE)
    assert ctx.opened == [RELEASE.page_url]


def test_on_android_the_apk_goes_to_download_and_the_installer_opens(android: None, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeDownloads([apk_update.RUNNING, apk_update.RUNNING, apk_update.SUCCESSFUL])
    monkeypatch.setattr(apk_update, "downloads", lambda: fake)
    ctx = FakeContext()
    apk_update.fetch(ctx, RELEASE)
    assert fake.started == [(RELEASE.apk_url, "ZibaldOne-0.3.3-android.apk")]
    assert fake.installed == [7] and not ctx.opened
    assert "Download" in ctx.toasts[-1] and "apk_download" not in ctx.memory


def test_a_failed_download_falls_back_to_the_browser(android: None, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeDownloads([apk_update.FAILED])
    monkeypatch.setattr(apk_update, "downloads", lambda: fake)
    ctx = FakeContext()
    apk_update.fetch(ctx, RELEASE)
    assert not fake.installed and ctx.opened == [RELEASE.apk_url]


def test_without_pyjnius_android_opens_the_apk_link(android: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(apk_update, "downloads", lambda: None)
    ctx = FakeContext()
    apk_update.fetch(ctx, RELEASE)
    assert ctx.opened == [RELEASE.apk_url]


def test_a_second_tap_while_downloading_does_not_start_another(android: None, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeDownloads([])
    monkeypatch.setattr(apk_update, "downloads", lambda: fake)
    ctx = FakeContext()
    ctx.memory["apk_download"] = True
    apk_update.fetch(ctx, RELEASE)
    assert not fake.started and not ctx.opened
