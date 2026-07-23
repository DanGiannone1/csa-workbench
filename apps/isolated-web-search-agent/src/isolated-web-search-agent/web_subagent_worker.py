import json
import os
import sys

from isolation_contracts import normalize_research_task
from web_research import MockWebProvider, WebResearchSubagent


LIVE_MODES = {"http", "https", "live", "web", "real"}


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _not_configured(task) -> dict:
    return {
        "status": "not_configured",
        "detail": "web_research_provider_disabled",
        "query": task.query,
        "allowedDomains": list(task.allowed_domains),
        "claims": [],
        "citations": [],
        "budgetUsed": {"iterations": 0, "fetches": 0},
        "guardrails": {
            "rawWebContentReturned": False,
            "privilegedToolsAvailable": False,
            "promptInjectionScan": "not_run",
        },
    }


def _select_provider(mode: str, task):
    if mode == "mock":
        provider = MockWebProvider()
        return provider, provider
    if mode in LIVE_MODES:
        from http_web_provider import DEFAULT_USER_AGENT, HttpWebProvider

        provider = HttpWebProvider(
            allowed_domains=task.allowed_domains,
            timeout=_float_env("WEB_RESEARCH_HTTP_TIMEOUT_SECONDS", 15.0),
            max_redirects=_int_env("WEB_RESEARCH_MAX_REDIRECTS", 3),
            max_bytes=_int_env("WEB_RESEARCH_MAX_BYTES", 200_000),
            user_agent=os.getenv("WEB_RESEARCH_USER_AGENT") or DEFAULT_USER_AGENT,
        )
        return provider, provider
    return None, None


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read())
        task = normalize_research_task(payload)
        mode = os.getenv("WEB_RESEARCH_MODE", "mock").strip().lower()
        search_provider, fetch_provider = _select_provider(mode, task)
        if search_provider is None:
            print(json.dumps(_not_configured(task)))
            return 0
        result = WebResearchSubagent(search_provider, fetch_provider).run(task)
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as exc:  # noqa: BLE001 - worker reports stable JSON to the harness
        print(json.dumps({"status": "error", "errorCode": "subagent_failure", "detail": type(exc).__name__}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())