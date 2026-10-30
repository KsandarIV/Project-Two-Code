import json
from datetime import datetime, timedelta, timezone

import pytest
from typer.testing import CliRunner

from zibaldone.cli.app import app
from zibaldone.cloud import updates
from zibaldone.cloud.http import CloudError, HttpResponse, OfflineError

NOW = datetime(2026, 10, 20, 9, 0, tzinfo=timezone.utc)
runner = CliRunner()


def release(tag, draft=False, apk=True):
    assets = [{"name": f"ZibaldOne-{tag}.apk", "browser_download_url": f"https://github.com/x/{tag}.apk"}] if apk else []
    return {"tag_name": tag, "draft": draft, "html_url": f"https://github.com/x/releases/{tag}", "assets": assets, "published_at": "2026-10-19T10:00:00Z", "body": "Novità"}


class FakeGitHub:
    def __init__(self, answer=None, status=200, offline=False):
        self.answer = answer if answer is not None else []
        self.status = status
        self.offline = offline
        self.calls = 0

    def request(self, method, url, headers=None, body=None, timeout=30):
        self.calls += 1
        assert url == updates.RELEASES_API and "ZibaldOne/" in headers["User-Agent"]
        if self.offline:
            raise OfflineError("nessuna connessione")
        return HttpResponse(self.status, json.dumps(self.answer).encode())


def test_version_code_always_grows():
    versions = ("0.0.9", "0.1.0", "0.1.5", "0.2.0", "0.3.2", "0.3.2.1", "0.3.2.12", "0.3.3", "0.10.0", "1.0.0", "1.0.1", "1.0.1.1", "1.1.0")
    codes = [updates.version_code(v) for v in versions]
    assert codes == sorted(set(codes))
    assert updates.version_code("0.3.2") == 300200 and updates.version_code("0.3.2.1") == 300201
    assert updates.version_code("0.3.2") > 3002  # the old code of 0.3.2: installed apps must still see an update
    with pytest.raises(ValueError):
        updates.version_code("1.0")


@pytest.mark.parametrize("text", ["1.0", "0.3.2.0", "0.3.2.100", "0.3.2.1.1", "0.100.0", "0.3.x", "v0.3.2", ""])
def test_invalid_versions_are_refused(text):
    with pytest.raises(ValueError):
        updates.parse_version(text)


def test_mini_patch_sorts_between_releases():
    assert updates.parse_version("0.3.2") < updates.parse_version("0.3.2.1") < updates.parse_version("0.3.2.2") < updates.parse_version("0.3.3")
    assert updates.parse_version(" 0.3.2.1 ") == (0, 3, 2, 1)


def test_update_check_sees_mini_patches():
    found = updates.releases_from([release("zibaldone-v0.3.2"), release("zibaldone-v0.3.2.1"), release("zibaldone-v0.3.1")])
    assert [item.version for item in found] == ["0.3.2.1", "0.3.2", "0.3.1"]
    assert updates.is_newer(found[0], "0.3.2") and not updates.is_newer(found[1], "0.3.2.1")


def test_only_zibaldone_releases_newest_first():
    data = [release("zibaldone-v0.1.0"), release("zibaldone-v0.1.2", draft=True), release("altro-v9.0.0"), release("zibaldone-v0.1.1", apk=False), release("zibaldone-vX")]
    found = updates.releases_from(data)
    assert [item.version for item in found] == ["0.1.1", "0.1.0"]
    assert found[0].apk_url is None and found[1].apk_url.endswith(".apk")


def test_check_now_saves_and_compares(isolated_data_dir):
    github = FakeGitHub([release("zibaldone-v0.1.1"), release("zibaldone-v0.1.0")])
    newer = updates.check_now(isolated_data_dir, current="0.1.0", http=github, now=NOW)
    assert newer.version == "0.1.1"
    assert updates.check_now(isolated_data_dir, current="0.1.1", http=github, now=NOW) is None
    assert updates.cached_release(isolated_data_dir, current="0.1.0").version == "0.1.1"


def test_maybe_check_once_a_day_and_never_raises(isolated_data_dir):
    github = FakeGitHub([release("zibaldone-v0.1.1")])
    assert updates.maybe_check(isolated_data_dir, "0.1.0", github, NOW).version == "0.1.1"
    assert updates.maybe_check(isolated_data_dir, "0.1.0", github, NOW + timedelta(hours=3)).version == "0.1.1"
    assert github.calls == 1
    offline = FakeGitHub(offline=True)
    assert updates.maybe_check(isolated_data_dir, "0.1.0", offline, NOW + timedelta(days=2)).version == "0.1.1"  # the cached answer
    updates.set_auto_check(isolated_data_dir, False)
    assert updates.maybe_check(isolated_data_dir, "0.1.0", github, NOW + timedelta(days=3)) is None
    assert github.calls == 1


def test_rate_limit_and_missing_repository_messages():
    with pytest.raises(CloudError, match="troppe richieste"):
        updates.latest_release(FakeGitHub(status=403))
    with pytest.raises(CloudError, match="privato"):
        updates.latest_release(FakeGitHub(status=404))
    assert updates.latest_release(FakeGitHub([])) is None


def test_cli_update(isolated_data_dir, monkeypatch):
    github = FakeGitHub([release("zibaldone-v9.9.9")])
    monkeypatch.setattr(updates, "UrllibHttp", lambda: github)
    assert runner.invoke(app, ["privacy", "accept"]).exit_code == 0
    result = runner.invoke(app, ["update"])
    assert result.exit_code == 0 and "9.9.9" in result.output and ".apk" in result.output
    github.answer = []
    assert "più recente" in runner.invoke(app, ["update"]).output
    off = runner.invoke(app, ["update", "--no-auto"])
    assert off.exit_code == 0 and not updates.auto_check_enabled(isolated_data_dir)
