import pytest

from zibaldone.cloud.http import OfflineError, UrllibHttp


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """Every test gets its own empty data folder, never the real one."""
    folder = tmp_path / "zibaldone-data"
    monkeypatch.setenv("ZIBALDONE_HOME", str(folder))
    return folder


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Tests never go online: the real HTTP client behaves as if there were no connection."""

    def offline(self, method, url, *args, **kwargs):
        raise OfflineError(f"test senza rete: {method} {url}")

    monkeypatch.setattr(UrllibHttp, "request", offline)
