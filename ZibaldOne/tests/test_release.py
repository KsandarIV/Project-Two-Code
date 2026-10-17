import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "release.py"
spec = importlib.util.spec_from_file_location("release", SCRIPT)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)

from zibaldone import __version__  # noqa: E402


def test_next_version_keywords() -> None:
    assert release.next_version("0.2.0", "patch") == "0.2.1"
    assert release.next_version("0.2.3", "minor") == "0.3.0"
    assert release.next_version("0.9.1", "major") == "1.0.0"
    assert release.next_version("0.2.0", "1.5.0") == "1.5.0"


def test_next_version_must_grow() -> None:
    with pytest.raises(release.ReleaseError):
        release.next_version("0.3.0", "0.2.9")
    with pytest.raises(release.ReleaseError):
        release.next_version("0.3.0", "tre")


def test_write_and_read_version() -> None:
    source = '"""Doc."""\n\n__version__ = "0.0.2"\n'
    assert release.read_version(release.write_version(source, "0.3.0")) == "0.3.0"


def test_changelog_moves_unreleased_entries() -> None:
    changelog = "# Changelog\n\n## [Unreleased]\n### Aggiunto\n- cosa nuova\n\n## [0.2.0] — 2026-10-17\n- vecchia\n"
    result = release.release_changelog(changelog, "0.3.0", "2026-10-18")
    assert "## [Unreleased]\n\n## [0.3.0] — 2026-10-18\n### Aggiunto\n- cosa nuova" in result
    assert "## [0.2.0] — 2026-10-17" in result


def test_changelog_keeps_existing_section() -> None:
    changelog = "## [Unreleased]\n\n## [0.3.0] — 2026-10-18\n- già scritta\n"
    assert release.release_changelog(changelog, "0.3.0", "2026-10-18") == changelog


def test_changelog_without_entries_fails() -> None:
    with pytest.raises(release.ReleaseError):
        release.release_changelog("## [Unreleased]\n\n## [0.2.0]\n", "0.3.0", "2026-10-18")


def test_current_version_is_documented() -> None:
    """Every released version has a CHANGELOG section and a note in docs/versioni."""
    root = SCRIPT.parent.parent
    assert f"## [{__version__}]" in (root / "CHANGELOG.md").read_text(encoding="utf-8")
    assert (root / "docs" / "versioni" / f"v{__version__}.md").exists()


def test_changelog_placeholder_for_automatic_commits() -> None:
    result = release.release_changelog("## [Unreleased]\n\n## [0.2.0]\n", "0.3.0", "2026-10-18", allow_empty=True)
    assert "## [0.3.0] — 2026-10-18\n" + release.EMPTY_NOTES in result


WATCH = SCRIPT.parent / "version_watch.py"


def test_watcher_commits_when_version_changes(tmp_path, monkeypatch) -> None:
    import shutil
    import subprocess
    import sys

    project = tmp_path / "repo" / "ZibaldOne"
    shutil.copytree(SCRIPT.parent.parent, project, ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__", "*.egg-info"))
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    root = project.parent
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=root, check=True)
    watcher = [sys.executable, str(project / "scripts" / "version_watch.py"), "--once"]

    subprocess.run(watcher, cwd=project, check=True)
    assert subprocess.run(["git", "tag"], cwd=root, capture_output=True, text=True).stdout == ""

    init_file = project / "src" / "zibaldone" / "__init__.py"
    current = release.read_version(init_file.read_text(encoding="utf-8"))
    newer = release.next_version(current, "patch")
    init_file.write_text(release.write_version(init_file.read_text(encoding="utf-8"), newer), encoding="utf-8")
    subprocess.run(watcher, cwd=project, check=True)
    tags = subprocess.run(["git", "tag"], cwd=root, capture_output=True, text=True).stdout.split()
    assert tags == [f"zibaldone-v{newer}"]
    log = subprocess.run(["git", "log", "--oneline", "-1"], cwd=root, capture_output=True, text=True).stdout
    assert f"release: ZibaldOne v{newer}" in log
