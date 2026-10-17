import pytest


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """Every test gets its own empty data folder, never the real one."""
    folder = tmp_path / "zibaldone-data"
    monkeypatch.setenv("ZIBALDONE_HOME", str(folder))
    return folder
