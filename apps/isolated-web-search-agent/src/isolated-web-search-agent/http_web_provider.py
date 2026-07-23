"""Real-web search and fetch provider for the isolated research subagent.

This provider runs inside the sanitized subprocess and reaches the public web
with no credentials. Search uses the keyless DuckDuckGo Instant Answer JSON API;
page fetches are hardened against SSRF:

- every target must pass ``ensure_public_https_url`` (https, public host, in the
  allowed-domain ceiling),
- the resolved DNS address is re-checked and rejected if it maps to a private,
  loopback, link-local, reserved, or multicast range (post-DNS SSRF re-check),
- redirects are capped and each hop is re-validated,
- responses are byte-capped and reduced to text before returning.

The DNS re-check is best effort: it narrows the SSRF window but does not pin the
connection to the validated IP, so a network-layer egress allowlist remains the
strongest control for production.
"""

from __future__ import annotations

import json
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from ipaddress import ip_address
from typing import Any, Callable

from isolation_contracts import ensure_public_https_url


DEFAULT_USER_AGENT = "isolated-web-search-agent/1.0 (+https://github.com/)"
DEFAULT_SEARCH_ENDPOINT = "https://api.duckduckgo.com/"
DEFAULT_TIMEOUT_SECONDS = 15.0
DEFAULT_MAX_REDIRECTS = 3
DEFAULT_MAX_BYTES = 200_000

_REDIRECT_STATUSES = {301, 302, 303, 307, 308}

Transport = Callable[[str, dict, float, int], "RawResponse"]
Resolver = Callable[[str], list[str]]


class RawResponse:
    __slots__ = ("status", "headers", "body")

    def __init__(self, status: int, headers: dict[str, str], body: bytes) -> None:
        self.status = status
        self.headers = headers
        self.body = body


def _build_no_redirect_opener() -> urllib.request.OpenerDirector:
    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
            return None

    return urllib.request.build_opener(_NoRedirect)


def _urllib_transport(url: str, headers: dict[str, str], timeout: float, max_bytes: int) -> RawResponse:
    opener = _build_no_redirect_opener()
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with opener.open(request, timeout=timeout) as response:
            body = response.read(max_bytes)
            return RawResponse(response.status, {k.lower(): v for k, v in response.headers.items()}, body)
    except urllib.error.HTTPError as err:
        try:
            body = err.read(max_bytes)
        except Exception:  # noqa: BLE001 - best-effort body read on error responses
            body = b""
        return RawResponse(err.code, {k.lower(): v for k, v in (err.headers or {}).items()}, body)
    except (urllib.error.URLError, OSError, ValueError):
        return RawResponse(0, {}, b"")


def _default_resolver(host: str) -> list[str]:
    infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    return [info[4][0] for info in infos]


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style", "noscript"):
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "noscript") and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip and data.strip():
            self._chunks.append(data.strip())

    def text(self) -> str:
        return " ".join(self._chunks)


def _html_to_text(body: bytes, limit: int) -> str:
    decoded = body.decode("utf-8", errors="replace")
    parser = _TextExtractor()
    try:
        parser.feed(decoded)
        collapsed = re.sub(r"\s+", " ", parser.text()).strip()
    except Exception:  # noqa: BLE001 - fall back to a crude tag strip
        collapsed = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", decoded)).strip()
    return collapsed[:limit]


def _extract_search_results(data: Any) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    seen: set[str] = set()

    def add(url: Any, title: Any, snippet: Any) -> None:
        if not isinstance(url, str) or not url.startswith("https://") or url in seen:
            return
        seen.add(url)
        results.append(
            {
                "title": (title if isinstance(title, str) and title else url)[:120],
                "url": url,
                "snippet": (snippet if isinstance(snippet, str) else "")[:280],
            }
        )

    if isinstance(data, dict):
        add(data.get("AbstractURL"), data.get("Heading"), data.get("AbstractText"))
        for topic in data.get("RelatedTopics") or []:
            if isinstance(topic, dict) and topic.get("Topics"):
                for item in topic["Topics"]:
                    if isinstance(item, dict):
                        add(item.get("FirstURL"), item.get("Text"), item.get("Text"))
            elif isinstance(topic, dict):
                add(topic.get("FirstURL"), topic.get("Text"), topic.get("Text"))
        for result in data.get("Results") or []:
            if isinstance(result, dict):
                add(result.get("FirstURL"), result.get("Text"), result.get("Text"))
    return results


class HttpWebProvider:
    """Keyless real-web ``SearchProvider`` + ``FetchProvider`` with SSRF hardening."""

    def __init__(
        self,
        *,
        allowed_domains: tuple[str, ...] | list[str] = (),
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_redirects: int = DEFAULT_MAX_REDIRECTS,
        max_bytes: int = DEFAULT_MAX_BYTES,
        user_agent: str = DEFAULT_USER_AGENT,
        search_endpoint: str = DEFAULT_SEARCH_ENDPOINT,
        transport: Transport | None = None,
        resolver: Resolver | None = None,
    ) -> None:
        self._allowed = tuple(allowed_domains or ())
        self._timeout = float(timeout)
        self._max_redirects = int(max_redirects)
        self._max_bytes = int(max_bytes)
        self._user_agent = user_agent or DEFAULT_USER_AGENT
        self._search_endpoint = search_endpoint
        self._transport = transport or _urllib_transport
        self._resolver = resolver or _default_resolver

    def search(self, query: str, top: int) -> list[dict[str, str]]:
        params = urllib.parse.urlencode(
            {
                "q": query,
                "format": "json",
                "no_html": "1",
                "no_redirect": "1",
                "t": "isolated-web-search-agent",
            }
        )
        endpoint = f"{self._search_endpoint}?{params}"
        try:
            raw = self._fetch_raw(endpoint, allowed=None, accept="application/json")
        except ValueError:
            return []
        if not raw:
            return []
        try:
            data = json.loads(raw.decode("utf-8", errors="replace"))
        except (ValueError, TypeError):
            return []
        return _extract_search_results(data)[: max(1, top)]

    def fetch(self, url: str) -> str:
        try:
            raw = self._fetch_raw(url, allowed=self._allowed, accept="text/html")
        except ValueError:
            return ""
        if not raw:
            return ""
        return _html_to_text(raw, self._max_bytes)

    def _headers(self, accept: str) -> dict[str, str]:
        return {
            "User-Agent": self._user_agent,
            "Accept": accept,
            "Accept-Language": "en-US,en;q=0.8",
        }

    def _assert_public_host(self, host: str) -> None:
        if not host:
            raise ValueError("url has no host")
        try:
            addresses = self._resolver(host)
        except OSError as exc:
            raise ValueError("host did not resolve") from exc
        if not addresses:
            raise ValueError("host did not resolve")
        for address in addresses:
            try:
                ip = ip_address(address)
            except ValueError as exc:
                raise ValueError("host resolved to an invalid address") from exc
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_reserved
                or ip.is_multicast
                or ip.is_unspecified
            ):
                raise ValueError("host resolves to a non-public address")

    def _fetch_raw(self, url: str, allowed: tuple[str, ...] | None, accept: str) -> bytes:
        current = url
        for _ in range(self._max_redirects + 1):
            safe = ensure_public_https_url(current, allowed_domains=allowed or None)
            host = urllib.parse.urlparse(safe).hostname or ""
            self._assert_public_host(host)
            response = self._transport(safe, self._headers(accept), self._timeout, self._max_bytes)
            if response.status in _REDIRECT_STATUSES:
                location = response.headers.get("location")
                if not location:
                    return b""
                current = urllib.parse.urljoin(safe, location)
                continue
            if response.status != 200:
                return b""
            return response.body
        return b""
