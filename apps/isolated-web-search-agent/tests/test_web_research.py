import importlib
import sys
from datetime import datetime
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = APP_ROOT / "src" / "isolated-web-search-agent"

if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

isolation_contracts = importlib.import_module("isolation_contracts")
isolation_runtime = importlib.import_module("isolation_runtime")
web_research = importlib.import_module("web_research")

normalize_research_task = isolation_contracts.normalize_research_task
run_research_in_subprocess = isolation_runtime.run_research_in_subprocess
MockWebProvider = web_research.MockWebProvider
WebResearchSubagent = web_research.WebResearchSubagent


def test_mock_subagent_returns_structured_findings_without_raw_content():
    task = normalize_research_task({"query": "agent web search isolation", "budget": {"maxFetches": 2}})
    provider = MockWebProvider()

    result = WebResearchSubagent(provider, provider).run(task)

    assert result["status"] == "ok"
    assert result["claims"]
    assert result["citations"]
    assert result["guardrails"]["rawWebContentReturned"] is False
    assert result["guardrails"]["privilegedToolsAvailable"] is False
    assert "External content can carry" not in str(result)


def test_subprocess_runtime_uses_sanitized_read_only_worker(monkeypatch):
    monkeypatch.setenv("WEB_RESEARCH_MODE", "mock")
    monkeypatch.setenv("SECRET_TOKEN", "should-not-cross")

    result = run_research_in_subprocess({"query": "agent web search isolation"}, timeout_seconds=10)

    assert result["status"] == "ok"
    assert "should-not-cross" not in str(result)
    assert result["guardrails"]["privilegedToolsAvailable"] is False


class _RecordingProvider:
    """Search + fetch provider that records every URL actually fetched."""

    def __init__(self, results: list[dict[str, str]]):
        self._results = results
        self.fetched: list[str] = []

    def search(self, query: str, top: int) -> list[dict[str, str]]:
        return self._results[:top]

    def fetch(self, url: str) -> str:
        self.fetched.append(url)
        return "benign public content"


def test_subagent_skips_non_public_fetch_targets():
    provider = _RecordingProvider([
        {"title": "cloud metadata", "url": "https://169.254.169.254/latest/meta-data", "snippet": "blocked"},
        {"title": "internal", "url": "http://intranet.local/secrets", "snippet": "blocked"},
        {"title": "public", "url": "https://owasp.org/", "snippet": "public source"},
    ])
    task = normalize_research_task({"query": "check ssrf handling", "budget": {"maxFetches": 5}})

    result = WebResearchSubagent(provider, provider).run(task)

    assert provider.fetched == ["https://owasp.org/"]
    cited_urls = [c["url"] for c in result["citations"]]
    assert cited_urls == ["https://owasp.org/"]
    assert all("169.254.169.254" not in url and ".local" not in url for url in cited_urls)


def test_subagent_respects_allowed_domains_before_fetching():
    provider = _RecordingProvider([
        {"title": "off-domain", "url": "https://owasp.org/", "snippet": "blocked by allowlist"},
        {"title": "on-domain", "url": "https://learn.microsoft.com/azure/", "snippet": "allowed"},
    ])
    task = normalize_research_task({
        "query": "scoped research",
        "allowedDomains": ["learn.microsoft.com"],
        "budget": {"maxFetches": 5},
    })

    result = WebResearchSubagent(provider, provider).run(task)

    assert provider.fetched == ["https://learn.microsoft.com/azure/"]
    assert [c["url"] for c in result["citations"]] == ["https://learn.microsoft.com/azure/"]


def test_budget_reports_real_iteration_count_and_action_gate():
    task = normalize_research_task({
        "query": "iteration accuracy",
        "budget": {"maxIterations": 3, "maxFetches": 10},
    })
    provider = MockWebProvider()

    result = WebResearchSubagent(provider, provider).run(task)

    assert result["budgetUsed"]["iterations"] >= 1
    assert result["budgetUsed"]["fetches"] == len(result["citations"])
    assert result["guardrails"]["actionGate"] == "requires_approval"
    assert result["guardrails"]["promptInjectionScan"] == "pass"


def test_all_blocked_targets_yield_degraded_status():
    provider = _RecordingProvider([
        {"title": "metadata", "url": "https://169.254.169.254/", "snippet": "blocked"},
        {"title": "internal", "url": "https://10.0.0.5/admin", "snippet": "blocked"},
    ])
    task = normalize_research_task({"query": "only private targets", "budget": {"maxFetches": 5}})

    result = WebResearchSubagent(provider, provider).run(task)

    assert provider.fetched == []
    assert result["status"] == "degraded"
    assert result["detail"] == "all_targets_blocked_pre_fetch"
    assert result["claims"] == []


def test_empty_provider_yields_degraded_no_results():
    provider = _RecordingProvider([])
    task = normalize_research_task({"query": "provider returns nothing"})

    result = WebResearchSubagent(provider, provider).run(task)

    assert result["status"] == "degraded"
    assert result["detail"] == "no_search_results"


def test_citations_carry_provenance_fields():
    task = normalize_research_task({"query": "provenance", "budget": {"maxFetches": 3}})
    provider = MockWebProvider()

    result = WebResearchSubagent(provider, provider).run(task)

    assert result["citations"]
    for citation in result["citations"]:
        assert citation["sourceTier"] in {"primary", "reputable", "unverified"}
        # retrievedAt must be a parseable ISO-8601 timestamp.
        datetime.fromisoformat(citation["retrievedAt"])
    tiers = {c["url"]: c["sourceTier"] for c in result["citations"]}
    assert tiers["https://owasp.org/www-project-top-10-for-large-language-model-applications/"] == "primary"