import importlib
import sys
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = APP_ROOT / "src" / "isolated-web-search-agent"

if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

http_web_provider = importlib.import_module("http_web_provider")

HttpWebProvider = http_web_provider.HttpWebProvider
RawResponse = http_web_provider.RawResponse


def _resolver(mapping):
    def resolve(host):
        if host in mapping:
            return list(mapping[host])
        raise OSError(f"unknown host: {host}")

    return resolve


def _transport(script):
    def transport(url, headers, timeout, max_bytes):
        entry = script.get(url)
        if entry is None:
            return RawResponse(0, {}, b"")
        return entry

    return transport


def test_search_parses_duckduckgo_json_and_filters_non_https():
    ddg_payload = (
        b'{"Heading":"OWASP","AbstractURL":"https://owasp.org/","AbstractText":"Security project",'
        b'"RelatedTopics":['
        b'{"FirstURL":"https://owasp.org/top10","Text":"OWASP Top 10"},'
        b'{"Topics":[{"FirstURL":"https://cheatsheetseries.owasp.org/","Text":"Cheat sheets"}]},'
        b'{"FirstURL":"http://insecure.example.com/","Text":"dropped (not https)"},'
        b'{"FirstURL":"https://owasp.org/","Text":"duplicate dropped"}'
        b']}'
    )
    endpoint = "https://api.duckduckgo.com/"

    def transport(url, headers, timeout, max_bytes):
        assert url.startswith(endpoint)
        return RawResponse(200, {}, ddg_payload)

    provider = HttpWebProvider(
        search_endpoint=endpoint,
        transport=transport,
        resolver=_resolver({"api.duckduckgo.com": ["93.184.216.34"]}),
    )

    results = provider.search("owasp", top=10)

    urls = [r["url"] for r in results]
    assert urls == [
        "https://owasp.org/",
        "https://owasp.org/top10",
        "https://cheatsheetseries.owasp.org/",
    ]
    assert results[0]["title"] == "OWASP"


def test_fetch_returns_stripped_text_for_ok_response():
    url = "https://owasp.org/"
    html = b"<html><head><style>.a{}</style></head><body><h1>Title</h1><p>Hello  world</p><script>x()</script></body></html>"
    provider = HttpWebProvider(
        transport=_transport({url: RawResponse(200, {"content-type": "text/html"}, html)}),
        resolver=_resolver({"owasp.org": ["93.184.216.34"]}),
    )

    text = provider.fetch(url)

    assert "Title" in text
    assert "Hello world" in text
    assert "x()" not in text


def test_fetch_follows_redirect_within_cap():
    start = "https://owasp.org/start"
    final = "https://owasp.org/final"
    provider = HttpWebProvider(
        transport=_transport(
            {
                start: RawResponse(302, {"location": final}, b""),
                final: RawResponse(200, {}, b"<p>arrived</p>"),
            }
        ),
        resolver=_resolver({"owasp.org": ["93.184.216.34"]}),
    )

    assert provider.fetch(start) == "arrived"


def test_fetch_caps_redirects():
    url = "https://owasp.org/loop"
    provider = HttpWebProvider(
        max_redirects=2,
        transport=_transport({url: RawResponse(302, {"location": url}, b"")}),
        resolver=_resolver({"owasp.org": ["93.184.216.34"]}),
    )

    assert provider.fetch(url) == ""


def test_fetch_rejects_non_https():
    provider = HttpWebProvider(
        transport=_transport({}),
        resolver=_resolver({"owasp.org": ["93.184.216.34"]}),
    )

    assert provider.fetch("http://owasp.org/") == ""


def test_fetch_blocks_post_dns_private_address():
    url = "https://internal.example.com/"
    provider = HttpWebProvider(
        transport=_transport({url: RawResponse(200, {}, b"<p>secret</p>")}),
        resolver=_resolver({"internal.example.com": ["10.0.0.5"]}),
    )

    assert provider.fetch(url) == ""


def test_fetch_blocks_redirect_to_private_address():
    start = "https://owasp.org/start"
    evil = "https://internal.example.com/"
    provider = HttpWebProvider(
        transport=_transport(
            {
                start: RawResponse(302, {"location": evil}, b""),
                evil: RawResponse(200, {}, b"<p>secret</p>"),
            }
        ),
        resolver=_resolver(
            {
                "owasp.org": ["93.184.216.34"],
                "internal.example.com": ["169.254.169.254"],
            }
        ),
    )

    assert provider.fetch(start) == ""


def test_fetch_respects_allowed_domain_ceiling():
    url = "https://owasp.org/page"
    provider = HttpWebProvider(
        allowed_domains=("learn.microsoft.com",),
        transport=_transport({url: RawResponse(200, {}, b"<p>content</p>")}),
        resolver=_resolver({"owasp.org": ["93.184.216.34"]}),
    )

    assert provider.fetch(url) == ""
