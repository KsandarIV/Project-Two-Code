import sys

import pytest

from zibaldone.storage import paths
from zibaldone.storage.settings import SettingsError, load_settings, save_settings


def test_env_variable_overrides_data_dir(isolated_data_dir) -> None:
    assert paths.data_dir() == isolated_data_dir


def test_windows_default_uses_appdata(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("ZIBALDONE_HOME")
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert paths.data_dir() == tmp_path / "ZibaldOne"


def test_human_size() -> None:
    assert paths.human_size(512) == "512 B"
    assert paths.human_size(1536) == "1.5 KB"
    assert paths.human_size(5 * 1024**3) == "5.0 GB"


def test_folder_usage_counts_files(tmp_path) -> None:
    (tmp_path / "a.txt").write_text("abc")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.txt").write_text("de")
    assert paths.folder_usage(tmp_path) == (2, 5)
    assert paths.folder_usage(tmp_path / "missing") == (0, 0)


def test_settings_round_trip_with_schema_version(tmp_path) -> None:
    save_settings(tmp_path, {"privacy": {"accepted": True}})
    loaded = load_settings(tmp_path)
    assert loaded["privacy"] == {"accepted": True}
    assert loaded["schema_version"] == 1
    assert not (tmp_path / "settings.tmp").exists()


def test_corrupt_settings_raise_clear_error(tmp_path) -> None:
    (tmp_path / "settings.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(SettingsError):
        load_settings(tmp_path)
