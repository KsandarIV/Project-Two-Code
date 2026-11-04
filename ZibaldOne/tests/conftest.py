import pytest

from zibaldone.cloud.http import OfflineError, UrllibHttp


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """Every test gets its own empty data folder, never the real one."""
    folder = tmp_path / "zibaldone-data"
    monkeypatch.setenv("ZIBALDONE_HOME", str(folder))
    for name in ("HOME", "USERPROFILE"):  # the folders where a backup file is looked for at first start
        monkeypatch.setenv(name, str(tmp_path / "home"))
    return folder


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Tests never go online: the real HTTP client behaves as if there were no connection."""

    def offline(self, method, url, *args, **kwargs):
        raise OfflineError(f"test senza rete: {method} {url}")

    monkeypatch.setattr(UrllibHttp, "request", offline)


@pytest.fixture(autouse=True)
def password_already_set(request, monkeypatch):
    """The main password page (KAN-29) comes before every other screen: tests of the other screens start after it.
    A test that asks for the `password_step` fixture sees the real page."""
    if "password_step" in request.fixturenames:
        return
    try:
        from zibaldone.ui import services
    except ImportError:  # no UI libraries installed
        return
    monkeypatch.setattr(services, "password_pending", lambda folder: False)


@pytest.fixture
def password_step():
    """Ask for this to keep the real main password page in the first start."""
    return True
