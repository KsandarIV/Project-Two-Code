"""Sign in with Google: OAuth 2.0 for installed apps, with PKCE and a loopback redirect.

The app opens the browser on Google's page; Google sends the browser back to
`http://127.0.0.1:<port>/` where a one-shot local server picks up the code.
No server of ours is involved. Scopes are kept minimal (ADR-0007): the
email to show who is signed in, and `drive.appdata`, the hidden app space on
the user's Drive, never the rest of their files.

The OAuth client (a "Desktop app" client from Google Cloud Console) is read
from, in order: the `ZIBALDONE_GOOGLE_CLIENT` variable (path to the JSON),
`google-client.json` in the data folder, `google_client.json` shipped inside
the package (written by the build, never committed).
"""

import base64
import hashlib
import html
import json
import os
import secrets
import threading
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from importlib import resources
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple
from urllib.parse import parse_qs, urlencode, urlparse

from zibaldone.cloud.http import CloudError, HttpClient, UrllibHttp, error_detail, form_body
from zibaldone.cloud.tokens import Tokens, expiry_from_now

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.appdata"
SCOPES = ("openid", "email", "profile", DRIVE_SCOPE)
CLIENT_ENV = "ZIBALDONE_GOOGLE_CLIENT"
CLIENT_FILE = "google-client.json"
PACKAGED_CLIENT = "google_client.json"
DEFAULT_TIMEOUT = 300.0

SUCCESS_PAGE = """<!doctype html><html lang="it"><meta charset="utf-8"><title>ZibaldOne</title>
<body style="background:#0D0E15;color:#E6F7FF;font-family:Segoe UI,Inter,sans-serif;text-align:center;padding-top:15vh">
<h1 style="color:#00E5FF">{title}</h1><p>{message}</p></body></html>"""


class AuthError(CloudError):
    """Sign-in failed or was cancelled."""


@dataclass(frozen=True)
class GoogleClient:
    client_id: str
    client_secret: str = ""

    def __repr__(self) -> str:
        return f"GoogleClient(client_id={self.client_id[:12]}…)"


@dataclass
class GoogleProfile:
    email: str
    name: str = ""
    subject: str = ""


def parse_client(data: Any) -> GoogleClient:
    """Accept the JSON downloaded from Google Cloud Console ({"installed": {...}}) or a flat one."""
    if isinstance(data, dict) and isinstance(data.get("installed"), dict):
        data = data["installed"]
    elif isinstance(data, dict) and isinstance(data.get("web"), dict):
        raise AuthError("il client Google è di tipo 'Web': serve un client di tipo 'App desktop'")
    if not isinstance(data, dict) or not isinstance(data.get("client_id"), str) or not data["client_id"].strip():
        raise AuthError("il file del client Google non contiene 'client_id'")
    secret = data.get("client_secret", "")
    return GoogleClient(client_id=data["client_id"].strip(), client_secret=secret if isinstance(secret, str) else "")


def _read_client_file(path: Path) -> GoogleClient:
    try:
        return parse_client(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError) as error:
        raise AuthError(f"non riesco a leggere il client Google in {path}: {error}") from None


def find_client(folder: Path) -> Optional[GoogleClient]:
    """The configured OAuth client, or None when sign-in with Google is not set up yet."""
    from_env = os.environ.get(CLIENT_ENV)
    if from_env:
        return _read_client_file(Path(from_env))
    local = folder / CLIENT_FILE
    if local.exists():
        return _read_client_file(local)
    try:
        packaged = resources.files("zibaldone.cloud").joinpath(PACKAGED_CLIENT)
        if packaged.is_file():
            return parse_client(json.loads(packaged.read_text(encoding="utf-8")))
    except (OSError, ValueError, ModuleNotFoundError):
        return None
    return None


# * — PKCE and URLs —


def make_pkce() -> Tuple[str, str]:
    """(verifier, S256 challenge) as in RFC 7636."""
    verifier = secrets.token_urlsafe(64)[:96]
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def authorization_url(client: GoogleClient, redirect_uri: str, challenge: str, state: str, login_hint: str = "") -> str:
    params = {
        "client_id": client.client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
    }
    if login_hint:
        params["login_hint"] = login_hint
    return f"{AUTH_URL}?{urlencode(params)}"


# * — token endpoint —


def _tokens_from(response_data: Dict[str, Any], previous_refresh: Optional[str] = None) -> Tokens:
    access = response_data.get("access_token")
    if not isinstance(access, str) or not access:
        raise AuthError("Google non ha restituito un token d'accesso")
    return Tokens(
        access_token=access,
        refresh_token=response_data.get("refresh_token") or previous_refresh,
        expires_at=expiry_from_now(response_data.get("expires_in", 3600)),
        scope=str(response_data.get("scope", "")),
    )


def exchange_code(http: HttpClient, client: GoogleClient, code: str, verifier: str, redirect_uri: str) -> Tokens:
    fields = {
        "code": code,
        "client_id": client.client_id,
        "code_verifier": verifier,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    if client.client_secret:
        fields["client_secret"] = client.client_secret
    response = http.request("POST", TOKEN_URL, {"Content-Type": "application/x-www-form-urlencoded"}, form_body(fields))
    if not response.ok:
        raise AuthError(f"Google ha rifiutato l'accesso ({error_detail(response)})")
    return _tokens_from(response.json())


def refresh_tokens(http: HttpClient, client: GoogleClient, tokens: Tokens) -> Tokens:
    """A new access token from the refresh token. In Google's test mode refresh
    tokens expire after about 7 days: then the user has to sign in again."""
    if not tokens.refresh_token:
        raise AuthError("l'accesso a Google è scaduto: entra di nuovo con `zbone account login`")
    fields = {"client_id": client.client_id, "refresh_token": tokens.refresh_token, "grant_type": "refresh_token"}
    if client.client_secret:
        fields["client_secret"] = client.client_secret
    response = http.request("POST", TOKEN_URL, {"Content-Type": "application/x-www-form-urlencoded"}, form_body(fields))
    if b"invalid_client" in response.body:
        raise AuthError(f"il client OAuth di questa copia di ZibaldOne non è valido ({error_detail(response)})")
    if response.status in (400, 401):
        raise AuthError("l'accesso a Google è scaduto: entra di nuovo con `zbone account login`")
    if not response.ok:
        raise AuthError(f"non riesco a rinnovare l'accesso a Google ({error_detail(response)})")
    return _tokens_from(response.json(), previous_refresh=tokens.refresh_token)


def fetch_profile(http: HttpClient, access_token: str) -> GoogleProfile:
    response = http.request("GET", USERINFO_URL, {"Authorization": f"Bearer {access_token}"})
    if not response.ok:
        raise AuthError(f"non riesco a leggere il profilo Google ({error_detail(response)})")
    data = response.json()
    email = data.get("email") if isinstance(data, dict) else None
    if not isinstance(email, str) or "@" not in email:
        raise AuthError("Google non ha restituito l'email dell'account")
    return GoogleProfile(email=email, name=str(data.get("name", "")), subject=str(data.get("sub", "")))


def revoke(http: HttpClient, tokens: Tokens) -> bool:
    """Ask Google to forget the app's access. Best effort: False when offline or refused."""
    token = tokens.refresh_token or tokens.access_token
    try:
        response = http.request("POST", REVOKE_URL, {"Content-Type": "application/x-www-form-urlencoded"}, form_body({"token": token}))
    except CloudError:
        return False
    return response.ok


# * — loopback redirect —


class _Catcher(BaseHTTPRequestHandler):
    result: Dict[str, str]
    done: threading.Event

    def do_GET(self) -> None:  # noqa: N802 (http.server API)
        query = parse_qs(urlparse(self.path).query)
        if not query:
            self.send_response(404)
            self.end_headers()
            return
        self.server.result = {key: values[0] for key, values in query.items()}  # type: ignore[attr-defined]
        if "code" in query:
            title, message = "Accesso completato", "Puoi chiudere questa scheda e tornare a ZibaldOne."
        else:
            title, message = "Accesso non riuscito", "Torna a ZibaldOne e riprova."
        page = SUCCESS_PAGE.format(title=html.escape(title), message=html.escape(message)).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(page)))
        self.end_headers()
        self.wfile.write(page)
        self.server.done.set()  # type: ignore[attr-defined]

    def log_message(self, *args: Any) -> None:  # keep the terminal clean, never log the code
        return


def _start_catcher() -> HTTPServer:
    server = HTTPServer(("127.0.0.1", 0), _Catcher)
    server.result = {}  # type: ignore[attr-defined]
    server.done = threading.Event()  # type: ignore[attr-defined]
    threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.2}, daemon=True).start()
    return server


def sign_in(
    client: GoogleClient,
    http: Optional[HttpClient] = None,
    open_browser: Callable[[str], Any] = webbrowser.open,
    timeout: float = DEFAULT_TIMEOUT,
    login_hint: str = "",
) -> Tuple[Tokens, GoogleProfile]:
    """The whole browser flow. Blocks until Google redirects back or `timeout` seconds pass."""
    http = http or UrllibHttp()
    server = _start_catcher()
    try:
        redirect_uri = f"http://127.0.0.1:{server.server_port}/"
        verifier, challenge = make_pkce()
        state = secrets.token_urlsafe(24)
        open_browser(authorization_url(client, redirect_uri, challenge, state, login_hint))
        if not server.done.wait(timeout):  # type: ignore[attr-defined]
            raise AuthError("accesso non completato in tempo: riprova")
        result: Dict[str, str] = server.result  # type: ignore[attr-defined]
    finally:
        server.shutdown()
        server.server_close()
    if result.get("state") != state:
        raise AuthError("risposta di Google non valida (state diverso): riprova")
    if "error" in result:
        reason = "hai annullato l'accesso" if result["error"] == "access_denied" else result["error"]
        raise AuthError(f"accesso non riuscito: {reason}")
    if "code" not in result:
        raise AuthError("Google non ha restituito il codice d'accesso")
    tokens = exchange_code(http, client, result["code"], verifier, redirect_uri)
    return tokens, fetch_profile(http, tokens.access_token)


def drive_granted(tokens: Tokens) -> bool:
    """Google lets the user untick the Drive permission; then only local mode is possible."""
    return DRIVE_SCOPE in tokens.scope.split() if tokens.scope else True
