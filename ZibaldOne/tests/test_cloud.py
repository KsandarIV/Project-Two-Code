"""Le Nuvole (0.0.8): Google sign-in, Drive and folder destinations, sync and recovery.

Google is replaced by `FakeGoogle`, an HttpClient that answers like the
token endpoint, the userinfo endpoint and Drive v3 (appDataFolder only).
The browser is replaced by a function that calls the local redirect page
directly, like Google would after the user clicks "Consenti".
"""

import base64
import hashlib
import json
import re
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import parse_qs, urlencode, urlparse

import pytest
import typer
from typer.testing import CliRunner

from zibaldone.cli import account_cmd
from zibaldone.cli.account_cmd import account_app, cloud_app
from zibaldone.cli.backup_cmd import backup_app
from zibaldone.cli.common import run_auto_backup
from zibaldone.cli.entry_cmd import entry_app
from zibaldone.cli.export_cmd import export_app
from zibaldone.cli.privacy_cmd import privacy_app
from zibaldone.cli.template_cmd import template_app
from zibaldone.cloud import account, google_auth, sync
from zibaldone.cloud import tokens as token_store
from zibaldone.cloud.destinations import GoogleDriveDestination, LocalFolderDestination
from zibaldone.cloud.google_auth import AuthError, GoogleClient
from zibaldone.cloud.http import CloudError, HttpResponse, error_detail
from zibaldone.core import crypto
from zibaldone.core.crypto import ScryptParams
from zibaldone.core.privacy import NOTICE_VERSION
from zibaldone.core.templates import BlockSpec, Template
from zibaldone.storage import backups, keys
from zibaldone.storage.backups import RetentionPolicy, BackupSettings, create_snapshot, save_backup_settings
from zibaldone.storage.database import Store
from zibaldone.storage.settings import load_settings, record_consent, save_settings

UTC = timezone.utc
PASSPHRASE = "cavallo batteria graffetta"
RECOVERY_CODE = crypto.recovery_code_from_bytes(bytes(range(15)))
LAST_GROUP = RECOVERY_CODE.split("-")[-1]
EMAIL = "alex@example.com"
CLIENT = {"installed": {"client_id": "1234-test.apps.googleusercontent.com", "client_secret": "not-really-secret"}}
LIBRO = Template("libro", "Libro", [BlockSpec("titolo", "text", "Titolo", required=True)])

app = typer.Typer()
for group, name in (
    (privacy_app, "privacy"),
    (template_app, "template"),
    (entry_app, "entry"),
    (backup_app, "backup"),
    (export_app, "export"),
    (account_app, "account"),
    (cloud_app, "cloud"),
):
    app.add_typer(group, name=name)
runner = CliRunner()


@pytest.fixture(autouse=True)
def fast_and_predictable(monkeypatch):
    monkeypatch.setattr(keys, "DEFAULT_SCRYPT_PARAMS", ScryptParams(n=2**10))
    monkeypatch.setattr(crypto, "generate_recovery_code", lambda: RECOVERY_CODE)
    monkeypatch.delenv(google_auth.CLIENT_ENV, raising=False)


# * — a fake Google —


class FakeGoogle:
    """Token endpoint, userinfo and Drive v3 in appDataFolder, in memory."""

    def __init__(self, email: str = EMAIL, scope: str = " ".join(google_auth.SCOPES)) -> None:
        self.email = email
        self.scope = scope
        self.files: Dict[str, Dict] = {}  # id -> {name, data, modified}
        self.sessions: Dict[str, Optional[str]] = {}  # upload url -> file id (None = new)
        self.pending_names: Dict[str, str] = {}
        self.valid_tokens = set()
        self.refresh_tokens = {"refresh-1"}
        self.counter = 0
        self.calls = []
        self.revoked = []
        self.codes = {}  # code -> PKCE challenge

    def _next(self, prefix: str) -> str:
        self.counter += 1
        return f"{prefix}-{self.counter}"

    def issue_token(self) -> str:
        token = self._next("access")
        self.valid_tokens.add(token)
        return token

    def expire_all(self) -> None:
        self.valid_tokens.clear()

    def _json(self, data, status: int = 200, headers: Optional[Dict[str, str]] = None) -> HttpResponse:
        return HttpResponse(status, json.dumps(data).encode("utf-8"), headers or {})

    def _authorized(self, headers: Dict[str, str]) -> bool:
        value = (headers or {}).get("Authorization", "")
        return value.startswith("Bearer ") and value[7:] in self.valid_tokens

    def request(self, method, url, headers=None, body=None, timeout=30):
        self.calls.append((method, url.split("?")[0]))
        parsed = urlparse(url)
        query = {key: values[0] for key, values in parse_qs(parsed.query).items()}
        base = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if base == google_auth.TOKEN_URL:
            return self._token(dict(parse_qs(body.decode("ascii"))))
        if base == google_auth.REVOKE_URL:
            self.revoked.append(parse_qs(body.decode("ascii"))["token"][0])
            return HttpResponse(200)
        if not self._authorized(headers):
            return self._json({"error": {"code": 401, "message": "Invalid Credentials"}}, 401)
        if base == google_auth.USERINFO_URL:
            return self._json({"email": self.email, "name": "Alex", "sub": "42"})
        return self._drive(method, base, query, headers or {}, body)

    def _token(self, form) -> HttpResponse:
        grant = form["grant_type"][0]
        if grant == "authorization_code":
            code = form["code"][0]
            challenge = self.codes.pop(code, None)
            verifier = form["code_verifier"][0]
            expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
            if challenge != expected:
                return self._json({"error": "invalid_grant", "error_description": "bad verifier"}, 400)
            return self._json({"access_token": self.issue_token(), "refresh_token": "refresh-1", "expires_in": 3599, "scope": self.scope})
        if grant == "refresh_token":
            if form["refresh_token"][0] not in self.refresh_tokens:
                return self._json({"error": "invalid_grant"}, 400)
            return self._json({"access_token": self.issue_token(), "expires_in": 3599, "scope": self.scope})
        return self._json({"error": "unsupported_grant_type"}, 400)

    def _by_name(self, name: str) -> Optional[str]:
        return next((file_id for file_id, item in self.files.items() if item["name"] == name), None)

    def _drive(self, method, base, query, headers, body) -> HttpResponse:
        files_url = "https://www.googleapis.com/drive/v3/files"
        upload_url = "https://www.googleapis.com/upload/drive/v3/files"
        if method == "GET" and base == files_url:
            assert query["spaces"] == "appDataFolder"
            items = [{"id": file_id, "name": item["name"], "size": str(len(item["data"])), "modifiedTime": item["modified"]} for file_id, item in self.files.items()]
            return self._json({"files": items})
        if method == "POST" and base == upload_url:
            metadata = json.loads(body)
            assert metadata["parents"] == ["appDataFolder"]
            session = f"https://upload.example/session/{self._next('s')}"
            self.sessions[session] = None
            self.pending_names[session] = metadata["name"]
            return HttpResponse(200, b"", {"Location": session})
        if method == "PATCH" and base.startswith(upload_url + "/"):
            file_id = base.rsplit("/", 1)[1]
            session = f"https://upload.example/session/{self._next('s')}"
            self.sessions[session] = file_id
            return HttpResponse(200, b"", {"Location": session})
        if method == "PUT" and base in self.sessions:
            file_id = self.sessions.pop(base)
            if file_id is None:
                file_id = self._next("file")
                self.files[file_id] = {"name": self.pending_names.pop(base), "data": b"", "modified": ""}
            self.files[file_id]["data"] = body
            self.files[file_id]["modified"] = datetime.now(UTC).isoformat()
            return self._json({"id": file_id, "name": self.files[file_id]["name"]})
        if base.startswith(files_url + "/"):
            file_id = base.rsplit("/", 1)[1]
            if file_id not in self.files:
                return self._json({"error": {"code": 404, "message": "File not found"}}, 404)
            if method == "GET" and query.get("alt") == "media":
                return HttpResponse(200, self.files[file_id]["data"])
            if method == "DELETE":
                del self.files[file_id]
                return HttpResponse(204)
        return self._json({"error": {"code": 400, "message": f"unexpected {method} {base}"}}, 400)

    def names(self):
        return sorted(item["name"] for item in self.files.values())


def browser_that_consents(google: FakeGoogle, **overrides):
    """Act like the user clicking "Consenti": Google redirects to the loopback page."""

    def open_browser(url: str) -> None:
        query = {key: values[0] for key, values in parse_qs(urlparse(url).query).items()}
        assert query["code_challenge_method"] == "S256"
        assert google_auth.DRIVE_SCOPE in query["scope"].split()
        code = "code-xyz"
        google.codes[code] = query["code_challenge"]
        answer = {"code": code, "state": query["state"], **overrides}
        answer = {key: value for key, value in answer.items() if value is not None}
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(f"{query['redirect_uri']}?{urlencode(answer)}", timeout=5) as response:
            assert response.status == 200

    return open_browser


def configure_client(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / google_auth.CLIENT_FILE).write_text(json.dumps(CLIENT), encoding="utf-8")


def signed_in(folder: Path, google: FakeGoogle) -> account.AccountStatus:
    configure_client(folder)
    return account.sign_in_with_google(folder, open_browser=browser_that_consents(google), timeout=10, http=google)


def add_books(folder: Path, *titles: str) -> None:
    with Store.open(folder) as store:
        if store.find_template("libro") is None:
            store.save_template(LIBRO)
        for title in titles:
            store.add_entry("libro", {"titolo": title}, day="2026-10-01")


def book_titles(folder: Path) -> list:
    with Store.open(folder) as store:
        return sorted(entry.values["titolo"] for entry in store.list_entries())


def encrypted_data(folder: Path, *titles: str) -> None:
    add_books(folder, *titles)
    keys.setup_keys(folder, PASSPHRASE)


# * — sign-in pieces —


def test_pkce_challenge_is_s256_of_the_verifier():
    verifier, challenge = google_auth.make_pkce()
    assert 43 <= len(verifier) <= 128
    assert challenge == base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    url = google_auth.authorization_url(GoogleClient("abc"), "http://127.0.0.1:5000/", challenge, "st4te", login_hint=EMAIL)
    query = parse_qs(urlparse(url).query)
    assert query["scope"][0].split() == list(google_auth.SCOPES)
    assert query["access_type"] == ["offline"] and query["login_hint"] == [EMAIL]


def test_client_file_must_be_a_desktop_client():
    assert google_auth.parse_client(CLIENT).client_id.startswith("1234")
    assert google_auth.parse_client({"client_id": "flat"}).client_secret == ""
    with pytest.raises(AuthError, match="App desktop"):
        google_auth.parse_client({"web": {"client_id": "x"}})
    with pytest.raises(AuthError, match="client_id"):
        google_auth.parse_client({"installed": {}})
    assert "secret" not in repr(google_auth.parse_client(CLIENT))


def test_no_client_means_no_login_required(isolated_data_dir):
    assert google_auth.find_client(isolated_data_dir) is None
    assert account.login_required(isolated_data_dir) is False
    configure_client(isolated_data_dir)
    assert account.login_required(isolated_data_dir) is True


def test_sign_in_saves_email_and_tokens_but_not_in_settings(isolated_data_dir):
    google = FakeGoogle()
    status = signed_in(isolated_data_dir, google)
    assert status.signed_in and status.email == EMAIL and status.drive_allowed
    assert account.login_required(isolated_data_dir) is False
    saved = token_store.load_tokens(isolated_data_dir)
    assert saved.refresh_token == "refresh-1" and saved.access_token in google.valid_tokens
    settings_text = (isolated_data_dir / "settings.json").read_text(encoding="utf-8")
    assert "refresh-1" not in settings_text and saved.access_token not in settings_text
    assert saved.access_token not in repr(saved)


def test_sign_in_refuses_a_wrong_state_and_reports_a_cancel(isolated_data_dir):
    configure_client(isolated_data_dir)
    google = FakeGoogle()
    with pytest.raises(AuthError, match="state"):
        account.sign_in_with_google(isolated_data_dir, browser_that_consents(google, state="forged"), timeout=10, http=google)
    with pytest.raises(AuthError, match="annullato"):
        account.sign_in_with_google(isolated_data_dir, browser_that_consents(google, code=None, error="access_denied"), timeout=10, http=google)
    assert not account.account_status(isolated_data_dir).signed_in


def test_without_drive_permission_only_local_or_folder(isolated_data_dir, tmp_path):
    google = FakeGoogle(scope="openid email profile")
    status = signed_in(isolated_data_dir, google)
    assert status.signed_in and not status.drive_allowed
    with pytest.raises(CloudError, match="Drive"):
        account.choose_mode(isolated_data_dir, "google")
    stick = tmp_path / "chiavetta"
    stick.mkdir()
    assert account.choose_mode(isolated_data_dir, "folder", str(stick)).mode == "folder"


def test_folder_mode_rejects_missing_or_inner_folders(isolated_data_dir, tmp_path):
    isolated_data_dir.mkdir()
    with pytest.raises(CloudError, match="non esiste"):
        account.choose_mode(isolated_data_dir, "folder", str(tmp_path / "nope"))
    inner = isolated_data_dir / "backups"
    inner.mkdir()
    with pytest.raises(CloudError, match="fuori"):
        account.choose_mode(isolated_data_dir, "folder", str(inner))
    with pytest.raises(CloudError, match="sconosciuta"):
        account.choose_mode(isolated_data_dir, "dropbox")


def test_expired_access_token_is_refreshed_and_saved(isolated_data_dir):
    google = FakeGoogle()
    signed_in(isolated_data_dir, google)
    saved = token_store.load_tokens(isolated_data_dir)
    saved.expires_at = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
    token_store.save_tokens(isolated_data_dir, saved)
    fresh = account.GoogleSession(isolated_data_dir, google).access_token()
    assert fresh != saved.access_token and fresh in google.valid_tokens
    assert token_store.load_tokens(isolated_data_dir).refresh_token == "refresh-1"
    google.refresh_tokens.clear()  # in Google's test mode refresh tokens expire after ~7 days
    with pytest.raises(AuthError, match="account login"):
        account.GoogleSession(isolated_data_dir, google).refresh()


def test_sign_out_revokes_and_goes_back_to_local(isolated_data_dir):
    google = FakeGoogle()
    signed_in(isolated_data_dir, google)
    account.choose_mode(isolated_data_dir, "google")
    assert account.sign_out(isolated_data_dir, google) is True
    assert google.revoked == ["refresh-1"]
    status = account.account_status(isolated_data_dir)
    assert not status.signed_in and status.mode == "local"
    assert token_store.load_tokens(isolated_data_dir) is None


def test_signing_in_with_another_account_leaves_google_mode(isolated_data_dir):
    signed_in(isolated_data_dir, FakeGoogle())
    account.choose_mode(isolated_data_dir, "google")
    status = signed_in(isolated_data_dir, FakeGoogle(email="amico@example.com"))
    assert status.email == "amico@example.com" and status.mode == "local"


def test_error_detail_never_echoes_the_request():
    response = HttpResponse(400, json.dumps({"error": "invalid_grant", "error_description": "Bad Request"}).encode())
    assert error_detail(response) == "HTTP 400: invalid_grant (Bad Request)"
    assert error_detail(HttpResponse(502, b"<html>")) == "HTTP 502"


# * — destinations —


def test_local_folder_destination_roundtrip(tmp_path):
    root = tmp_path / "chiavetta"
    root.mkdir()
    destination = LocalFolderDestination(root)
    destination.upload("a.zbsnap", b"uno")
    destination.upload("a.zbsnap", b"uno-bis")
    assert [(item.name, item.size) for item in destination.list_files()] == [("a.zbsnap", 7)]
    assert destination.download("a.zbsnap") == b"uno-bis"
    assert destination.delete("a.zbsnap") is True and destination.delete("a.zbsnap") is False
    with pytest.raises(CloudError, match="nome"):
        destination.upload("../fuori", b"x")
    with pytest.raises(CloudError, match="scollegata"):
        LocalFolderDestination(tmp_path / "staccata").upload("a.zbsnap", b"x")


def test_drive_destination_roundtrip_and_one_refresh_on_401():
    google = FakeGoogle()
    token = {"value": google.issue_token()}
    refreshed = []

    def refresh():
        token["value"] = google.issue_token()
        refreshed.append(token["value"])
        return token["value"]

    drive = GoogleDriveDestination(google, lambda: token["value"], refresh, email=EMAIL)
    drive.upload("keys.json", b"{}")
    drive.upload("keys.json", b'{"v": 2}')  # same file, updated with PATCH
    assert google.names() == ["keys.json"]
    assert drive.download("keys.json") == b'{"v": 2}'
    google.expire_all()
    assert [item.name for item in drive.list_files()] == ["keys.json"]
    assert len(refreshed) == 1
    assert drive.delete("keys.json") is True and drive.delete("keys.json") is False
    assert "alex@example.com" in drive.label


def test_drive_says_when_access_is_gone():
    google = FakeGoogle()
    drive = GoogleDriveDestination(google, lambda: "revoked-token")
    with pytest.raises(CloudError, match="account login"):
        drive.list_files()


# * — sync —


def test_nothing_leaves_the_device_unencrypted(isolated_data_dir, tmp_path):
    add_books(isolated_data_dir, "Zibaldone")
    create_snapshot(isolated_data_dir)
    stick = tmp_path / "chiavetta"
    stick.mkdir()
    destination = LocalFolderDestination(stick)
    with pytest.raises(CloudError, match="backup setup"):
        sync.sync_now(isolated_data_dir, destination)
    assert destination.list_files() == []


def test_sync_uploads_only_what_is_missing_and_prunes_remote(isolated_data_dir, tmp_path):
    encrypted_data(isolated_data_dir, "Zibaldone")
    save_backup_settings(isolated_data_dir, BackupSettings(retention=RetentionPolicy(daily=2, weekly=0, monthly=0)))
    start = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)
    first = [create_snapshot(isolated_data_dir, "auto", now=start + timedelta(days=day)) for day in range(3)]
    stick = tmp_path / "chiavetta"
    stick.mkdir()
    destination = LocalFolderDestination(stick)
    result = sync.sync_now(isolated_data_dir, destination)
    assert sorted(result.uploaded) == sorted(item.id for item in first)
    assert result.deleted == []  # what the device still keeps stays on the destination too
    assert result.remote_count == 3 and "3 in tutto" in result.message
    backups.prune(isolated_data_dir)  # the oldest daily copy is over the retention of 2
    again = sync.sync_now(isolated_data_dir, destination)
    assert again.uploaded == [] and again.deleted == [first[0].id]
    assert again.remote_count == 2
    names = {item.name for item in destination.list_files()}
    assert sync.REMOTE_KEYS in names
    status = account.account_status(isolated_data_dir)
    assert status.last_sync and status.last_sync_error is None


def test_sync_refuses_the_backups_of_another_key(isolated_data_dir, tmp_path):
    stick = tmp_path / "chiavetta"
    stick.mkdir()
    other = tmp_path / "altro-dispositivo"
    encrypted_data(other, "Altro")
    create_snapshot(other)
    sync.sync_now(other, LocalFolderDestination(stick))
    encrypted_data(isolated_data_dir, "Mio")
    with pytest.raises(CloudError, match="altra chiave"):
        sync.sync_now(isolated_data_dir, LocalFolderDestination(stick))
    assert "altra chiave" in account.account_status(isolated_data_dir).last_sync_error


def test_maybe_sync_never_raises(isolated_data_dir, tmp_path):
    encrypted_data(isolated_data_dir, "Zibaldone")
    stick = tmp_path / "chiavetta"
    stick.mkdir()
    account.choose_mode(isolated_data_dir, "folder", str(stick))
    stick.rmdir()  # the USB stick was unplugged
    assert sync.maybe_sync(isolated_data_dir) is None
    assert "scollegata" in account.account_status(isolated_data_dir).last_sync_error
    account.choose_mode(isolated_data_dir, "local")
    assert sync.maybe_sync(isolated_data_dir) is None


def test_new_device_recovers_with_the_passphrase(isolated_data_dir, tmp_path):
    stick = tmp_path / "chiavetta"
    stick.mkdir()
    old = tmp_path / "vecchio-pc"
    encrypted_data(old, "Canti", "Operette morali")
    create_snapshot(old)
    sync.sync_now(old, LocalFolderDestination(stick))
    remote = sync.list_remote(old, LocalFolderDestination(stick))
    assert len(remote) == 1 and remote[0].encrypted

    with pytest.raises(keys.WrongSecretError):
        sync.recover_from_cloud(isolated_data_dir, passphrase="non è questa la frase", destination=LocalFolderDestination(stick))
    result = sync.recover_from_cloud(isolated_data_dir, passphrase=PASSPHRASE, destination=LocalFolderDestination(stick))
    assert result.undo is None
    assert book_titles(isolated_data_dir) == ["Canti", "Operette morali"]
    assert keys.key_id(isolated_data_dir) == keys.key_id(old)


def test_new_device_recovers_with_the_recovery_code(isolated_data_dir, tmp_path):
    stick = tmp_path / "chiavetta"
    stick.mkdir()
    old = tmp_path / "vecchio-pc"
    add_books(old, "Canti")
    new_keys = keys.create_keys(PASSPHRASE)
    keys.save_new_keys(old, new_keys)
    create_snapshot(old)
    sync.sync_now(old, LocalFolderDestination(stick))
    sync.recover_from_cloud(isolated_data_dir, recovery_code=new_keys.recovery_code, destination=LocalFolderDestination(stick))
    assert book_titles(isolated_data_dir) == ["Canti"]


def test_google_recovery_opens_backups_with_the_account_only(isolated_data_dir, tmp_path):
    google = FakeGoogle()
    old = tmp_path / "vecchio-pc"
    signed_in(old, google)
    encrypted_data(old, "Zibaldone di pensieri")
    account.choose_mode(old, "google")
    create_snapshot(old)
    sync.sync_now(old, http=google)
    with pytest.raises(keys.WrongSecretError):
        sync.enable_google_recovery(old, "passphrase sbagliata", http=google)
    sync.enable_google_recovery(old, PASSPHRASE, http=google)
    assert sync.REMOTE_RECOVERY in google.names()
    assert account.account_status(old).google_recovery

    signed_in(isolated_data_dir, google)
    account.choose_mode(isolated_data_dir, "google")
    assert sync.google_recovery_available(isolated_data_dir, http=google)
    sync.recover_from_cloud(isolated_data_dir, http=google)
    assert book_titles(isolated_data_dir) == ["Zibaldone di pensieri"]

    sync.disable_google_recovery(old, http=google)
    assert sync.REMOTE_RECOVERY not in google.names()
    assert sync.SECRET_NAME not in keys.secret_names(old)
    assert not sync.google_recovery_available(old, http=google)


def test_forget_remote_deletes_only_zibaldone_files(isolated_data_dir, tmp_path):
    stick = tmp_path / "chiavetta"
    stick.mkdir()
    encrypted_data(isolated_data_dir, "Zibaldone")
    create_snapshot(isolated_data_dir)
    destination = LocalFolderDestination(stick)
    sync.sync_now(isolated_data_dir, destination)
    destination.upload("appunti.txt", b"non mio")
    assert sync.forget_remote(isolated_data_dir, destination) == 2
    assert [item.name for item in destination.list_files()] == ["appunti.txt"]
    assert backups.list_snapshots(isolated_data_dir)  # local backups stay


# * — command line —


def invoke(*args, input=None):
    return runner.invoke(app, list(args), input=input)


@pytest.fixture
def fake_google(monkeypatch):
    google = FakeGoogle()
    monkeypatch.setattr(account, "UrllibHttp", lambda: google)
    monkeypatch.setattr(account_cmd.webbrowser, "open", browser_that_consents(google))
    monkeypatch.setattr(google_auth, "DEFAULT_TIMEOUT", 10)
    return google


def test_first_start_offers_sign_in_and_saying_no_goes_on_locally(isolated_data_dir, fake_google):
    configure_client(isolated_data_dir)
    assert invoke("privacy", "accept").exit_code == 0
    declined = invoke("template", "list", input="no\n")
    assert declined.exit_code == 0, declined.output
    assert "non è obbligatorio" in declined.output and "continui solo in locale" in declined.output and "zbone account login" in declined.output
    assert not account.login_required(isolated_data_dir) and account.account_status(isolated_data_dir).login_skipped
    assert "account Google" not in invoke("template", "list").output  # no more questions
    exported = invoke("export", "markdown")  # getting the data back never needs Google
    assert exported.exit_code == 0, exported.output
    later = invoke("account", "login", input="no\n")  # the explicit login still works
    assert later.exit_code == 0, later.output
    assert f"Sei entrato come {EMAIL}" in later.output
    assert account.account_status(isolated_data_dir).mode == "local" and not account.account_status(isolated_data_dir).login_skipped


def test_first_start_saying_yes_signs_in(isolated_data_dir, fake_google):
    configure_client(isolated_data_dir)
    assert invoke("privacy", "accept").exit_code == 0
    accepted = invoke("template", "list", input="sì\nno\n")
    assert accepted.exit_code == 0, accepted.output
    assert f"Sei entrato come {EMAIL}" in accepted.output and "solo locale" in accepted.output
    assert account.account_status(isolated_data_dir).signed_in
    assert "account Google" not in invoke("template", "list").output


def test_signing_out_does_not_bring_the_question_back(isolated_data_dir, fake_google):
    configure_client(isolated_data_dir)
    signed_in(isolated_data_dir, fake_google)
    account.sign_out(isolated_data_dir, fake_google)
    assert account.account_status(isolated_data_dir).login_skipped and not account.login_required(isolated_data_dir)


def test_cli_folder_copies_start_with_encryption(isolated_data_dir, tmp_path, fake_google):
    stick = tmp_path / "chiavetta"
    stick.mkdir()
    assert invoke("privacy", "accept").exit_code == 0
    assert invoke("template", "create", "Libro", "--block", "titolo:text:Titolo!").exit_code == 0
    chosen = invoke("cloud", "use", "folder", str(stick))
    assert chosen.exit_code == 0, chosen.output
    assert "backup setup" in chosen.output
    setup = invoke("backup", "setup", input=f"{PASSPHRASE}\n{PASSPHRASE}\n{LAST_GROUP}\n")
    assert setup.exit_code == 0, setup.output
    assert "Sincronizzato con cartella" in setup.output
    listed = invoke("cloud", "list")
    assert listed.exit_code == 0 and "cifrata" in listed.output
    status = invoke("cloud")
    assert "locale + una cartella" in status.output and "Ultima copia" in status.output


def test_cli_automatic_backup_also_copies(isolated_data_dir, tmp_path, fake_google):
    stick = tmp_path / "chiavetta"
    stick.mkdir()
    encrypted_data(isolated_data_dir, "Zibaldone")
    record_consent(isolated_data_dir, accepted=True, notice_version=NOTICE_VERSION)
    account.choose_mode(isolated_data_dir, "folder", str(stick))
    run_auto_backup()
    remote = sync.list_remote(isolated_data_dir)
    assert len(remote) == 1


def test_cli_google_with_recovery_and_a_new_device(isolated_data_dir, tmp_path, fake_google, monkeypatch):
    assert invoke("privacy", "accept").exit_code == 0
    assert invoke("template", "create", "Libro", "--block", "titolo:text:Titolo!").exit_code == 0
    assert invoke("entry", "add", "libro", "--set", "titolo=Canti").exit_code == 0
    assert invoke("backup", "setup", input=f"{PASSPHRASE}\n{PASSPHRASE}\n{LAST_GROUP}\n").exit_code == 0
    created = invoke("backup", "create")  # the daily one was taken before "Canti"
    assert created.exit_code == 0
    manual_id = re.search(r"\d{8}T\d{6}Z-[0-9a-f]{6}", created.output).group(0)
    configure_client(isolated_data_dir)
    login = invoke("account", "login", input="sì\nsì\n" + PASSPHRASE + "\n")
    assert login.exit_code == 0, login.output
    assert "accounts.google.com" in login.output and "Recupero con Google attivo" in login.output
    assert "Sincronizzato con Google Drive" in login.output
    assert sync.REMOTE_RECOVERY in fake_google.names()

    new_device = tmp_path / "nuovo-telefono"
    monkeypatch.setenv("ZIBALDONE_HOME", str(new_device))
    configure_client(new_device)
    assert invoke("privacy", "accept").exit_code == 0
    assert invoke("account", "login", input="sì\n").exit_code == 0
    recovered = invoke("cloud", "recover", manual_id[-6:], input="sì\n")
    assert recovered.exit_code == 0, recovered.output
    assert book_titles(new_device) == ["Canti"]

    forget = invoke("cloud", "forget", "--yes")
    assert forget.exit_code == 0 and fake_google.names() == []
    logout = invoke("account", "logout", "--yes")
    assert logout.exit_code == 0 and "Sei uscito" in logout.output

