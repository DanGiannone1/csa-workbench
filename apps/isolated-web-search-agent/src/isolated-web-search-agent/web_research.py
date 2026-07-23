from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from isolation_contracts import (
    ResearchTask,
    classify_source_tier,
    detect_prompt_injection,
    ensure_public_https_url,
    validate_findings_payload,
)


class SearchProvider(Protocol):
    def search(self, query: str, top: int) -> list[dict[str, str]]:
        ...


class FetchProvider(Protocol):
    def fetch(self, url: str) -> str:
        ...


@dataclass(frozen=True)
class MockWebProvider:
    def search(self, query: str, top: int) -> list[dict[str, str]]:
        return [
            {
                "title": "OWASP LLM prompt injection guidance",
                "url": "https://owasp.org/www-project-top-10-for-large-language-model-applications/",
                "snippet": "Treat model inputs from external content as untrusted and constrain tool capability.",
            },
            {
                "title": "Microsoft guidance for agent security",
                "url": "https://learn.microsoft.com/azure/ai-foundry/",
                "snippet": "Use managed identity, least privilege, tracing, and policy boundaries for agent workloads.",
            },
            {
                "title": "Architecture note on isolated research",
                "url": "https://example.com/isolated-agent-research",
                "snippet": "Research loops are context-heavy and should return structured claims with citations.",
            },
        ][:top]

    def fetch(self, url: str) -> str:
        pages = {
            "https://owasp.org/www-project-top-10-for-large-language-model-applications/": (
                "External content can carry prompt injection attempts. Agentic systems should limit tools, "
                "validate outputs, and require human review for high-impact actions."
            ),
            "https://learn.microsoft.com/azure/ai-foundry/": (
                "Foundry agent applications should use explicit tools, observability, identity controls, "
                "and policy enforcement around model and tool boundaries."
            ),
            "https://example.com/isolated-agent-research": (
                "A dedicated research subagent can iterate over noisy web pages, distill findings with citations, "
                "and discard raw context before returning to the orchestrator."
            ),
        }
        return pages.get(url, "")


@dataclass
class WebResearchSubagent:
    search_provider: SearchProvider
    fetch_provider: FetchProvider

    def run(self, task: ResearchTask) -> dict:
        claims: list[dict[str, str]] = []
        citations: list[dict[str, str]] = []
        fetched_urls: set[str] = set()
        fetches = 0
        results_seen = 0
        blocked_pre_fetch = 0
        injection_blocked = 0
        iterations_run = 0
        allowed = task.allowed_domains or None
        query = task.query

        for iteration in range(max(1, task.budget.max_iterations)):
            if fetches >= task.budget.max_fetches:
                break
            iterations_run += 1
            remaining = task.budget.max_fetches - fetches
            results = self.search_provider.search(query, top=max(1, min(remaining, 3)))
            if not results:
                break
            fetched_this_round = 0
            for result in results:
                if fetches >= task.budget.max_fetches:
                    break
                url = result.get("url", "")
                if url in fetched_urls:
                    continue
                results_seen += 1
                # Pre-fetch egress control: never let the subagent reach a
                # non-public or out-of-scope host (SSRF defense).
                try:
                    safe_url = ensure_public_https_url(url, allowed_domains=allowed)
                except ValueError:
                    blocked_pre_fetch += 1
                    fetched_urls.add(url)
                    continue
                content = self.fetch_provider.fetch(safe_url)
                fetches += 1
                fetched_urls.add(url)
                fetched_this_round += 1
                if detect_prompt_injection(content):
                    injection_blocked += 1
                    continue
                snippet = result.get("snippet", "")[:280]
                citations.append({
                    "id": f"c{len(citations) + 1}",
                    "title": result.get("title", "Untitled"),
                    "url": safe_url,
                    "snippet": snippet,
                    "contentDigest": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                    "sourceTier": classify_source_tier(safe_url, allowed),
                    "retrievedAt": _utc_now_iso(),
                })
                claims.append({
                    "text": _claim_from_snippet(snippet),
                    "citationIds": [citations[-1]["id"]],
                    "confidence": "medium",
                })
            if fetched_this_round == 0:
                break
            query = _reformulate_query(task.query, iteration)

        scanned = fetches > 0
        status = "ok" if claims else "degraded"
        payload = {
            "status": status,
            "query": task.query,
            "allowedDomains": list(task.allowed_domains),
            "claims": claims,
            "citations": citations,
            "budgetUsed": {"iterations": iterations_run, "fetches": fetches},
            "guardrails": {
                "rawWebContentReturned": False,
                "privilegedToolsAvailable": False,
                "promptInjectionScan": "pass" if scanned else "not_run",
                "promptInjectionBlocked": injection_blocked,
                "actionGate": "requires_approval",
            },
        }
        if status == "degraded":
            payload["detail"] = _degraded_reason(results_seen, fetches, blocked_pre_fetch, injection_blocked)
        return validate_findings_payload(payload, max_chars=task.budget.max_findings_chars)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _degraded_reason(results_seen: int, fetches: int, blocked_pre_fetch: int, injection_blocked: int) -> str:
    if results_seen == 0:
        return "no_search_results"
    if fetches == 0 and blocked_pre_fetch > 0:
        return "all_targets_blocked_pre_fetch"
    if fetches > 0 and injection_blocked >= fetches:
        return "all_content_blocked"
    return "no_usable_claims"


def _reformulate_query(base_query: str, iteration: int) -> str:
    return f"{base_query} (follow-up {iteration + 1})"


def _claim_from_snippet(snippet: str) -> str:
    text = snippet.strip().rstrip(".")
    if not text:
        return "The source did not provide a usable summary"
    return f"{text}."