"""A tiny HTTP layer on the standard library, so the cloud code needs no extra
dependency and tests can swap in a fake server."""

import json
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Protocol
from urllib.parse import urlencode

DEFAULT_TIMEOUT = 30.0


class CloudError(Exception):
    """A cloud operation failed. Messages are for the user, in Italian."""


class OfflineError(CloudError):
    """No connection, DNS failure or timeout: worth retrying later."""


@dataclass
class HttpResponse:
    status: int
    body: bytes = b""
    headers: Dict[str, str] = field(default_factory=dict)

    def header(self, name: str) -> Optional[str]:
        wanted = name.lower()
        for key, value in self.headers.items():
            if key.lower() == wanted:
                return value
        return None

    def json(self) -> Any:
        try:
            return json.loads(self.body.decode("utf-8") or "null")
        except (UnicodeDecodeError, ValueError):
            raise CloudError("il server ha risposto con dati non validi") from None

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300


class HttpClient(Protocol):
    def request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        body: Optional[bytes] = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> HttpResponse: ...


class UrllibHttp:
    """The real client. HTTP errors come back as responses; network problems raise OfflineError."""

    def __init__(self, context: Optional[ssl.SSLContext] = None) -> None:
        self.context = context or ssl.create_default_context()

    def request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        body: Optional[bytes] = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> HttpResponse:
        request = urllib.request.Request(url, data=body, method=method, headers=headers or {})
        try:
            with urllib.request.urlopen(request, timeout=timeout, context=self.context) as response:
                return HttpResponse(response.status, response.read(), dict(response.headers.items()))
        except urllib.error.HTTPError as error:
            return HttpResponse(error.code, error.read() or b"", dict(error.headers.items()) if error.headers else {})
        except (urllib.error.URLError, TimeoutError, ConnectionError, ssl.SSLError) as error:
            reason = getattr(error, "reason", error)
            raise OfflineError(f"nessuna connessione con il server ({reason}). Riprova quando sei online") from None


def form_body(fields: Dict[str, str]) -> bytes:
    return urlencode(fields).encode("ascii")


def json_body(data: Any) -> bytes:
    return json.dumps(data, ensure_ascii=False).encode("utf-8")


def error_detail(response: HttpResponse) -> str:
    """A short, safe description of an error response (never the request, which may hold tokens)."""
    try:
        data = json.loads(response.body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return f"HTTP {response.status}"
    if isinstance(data, dict):
        error = data.get("error")
        if isinstance(error, dict):
            return f"HTTP {response.status}: {error.get('message', '')}".strip(": ")
        if isinstance(error, str):
            description = data.get("error_description", "")
            return f"HTTP {response.status}: {error}" + (f" ({description})" if description else "")
    return f"HTTP {response.status}"
