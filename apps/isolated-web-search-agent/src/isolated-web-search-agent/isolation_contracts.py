import ipaddress
import json
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse


MAX_QUERY_LENGTH = 800
MAX_ALLOWED_DOMAINS = 20
MAX_ITERATIONS = 10
MAX_FETCHES = 20
MAX_FINDINGS_CHARS = 20_000

SECRET_PATTERNS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", re.IGNORECASE),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{20,}\b", re.IGNORECASE),
    re.compile(r"\b(?:api[_-]?key|secret|password|token)\s*[:=]\s*\S+", re.IGNORECASE),
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
]

INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions", re.IGNORECASE),
    re.compile(r"reveal\s+(?:the\s+)?(?:system|developer)\s+prompt", re.IGNORECASE),
    re.compile(r"exfiltrat(?:e|ion)|send\s+.*(?:secret|credential|token)", re.IGNORECASE),
    re.compile(r"run\s+(?:this\s+)?(?:command|tool)|call\s+(?:the\s+)?tool", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(?:a|an)\s+", re.IGNORECASE),
]

BLOCKED_HOSTS = {"localhost", "localhost.localdomain"}

FINDINGS_STATUSES = {"ok", "degraded", "not_configured", "blocked", "error"}

SOURCE_TIERS = {"primary", "reputable", "unverified"}
AUTHORITATIVE_SUFFIXES = (".gov", ".edu", ".int", ".mil")
AUTHORITATIVE_DOMAINS = {
    "owasp.org",
    "microsoft.com",
    "learn.microsoft.com",
    "ietf.org",
    "w3.org",
    "nist.gov",
    "iso.org",
    "python.org",
}


@dataclass(frozen=True)
class ResearchBudget:
    max_iterations: int = 5
    max_fetches: int = 8
    max_findings_chars: int = 12_000

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ResearchBudget":
        budget = payload.get("budget") or {}
        return cls(
            max_iterations=_bounded_int(budget.get("maxIterations", 5), 1, MAX_ITERATIONS, "maxIterations"),
            max_fetches=_bounded_int(budget.get("maxFetches", 8), 1, MAX_FETCHES, "maxFetches"),
            max_findings_chars=_bounded_int(
                budget.get("maxFindingsChars", 12_000), 1_000, MAX_FINDINGS_CHARS, "maxFindingsChars"
            ),
        )


@dataclass(frozen=True)
class ResearchTask:
    query: str
    allowed_domains: tuple[str, ...] = field(default_factory=tuple)
    budget: ResearchBudget = field(default_factory=ResearchBudget)

    def to_wire(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "allowedDomains": list(self.allowed_domains),
            "budget": {
                "maxIterations": self.budget.max_iterations,
                "maxFetches": self.budget.max_fetches,
                "maxFindingsChars": self.budget.max_findings_chars,
            },
        }


def normalize_research_task(payload: dict[str, Any]) -> ResearchTask:
    if not isinstance(payload, dict):
        raise ValueError("task must be a JSON object")
    query = payload.get("query")
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query is required")
    query = _single_line(query.strip())
    if len(query) > MAX_QUERY_LENGTH:
        raise ValueError("query is too long")
    leaked = detect_sensitive_content(query)
    if leaked:
        raise ValueError(f"task query appears to contain sensitive content: {', '.join(leaked)}")

    domains = payload.get("allowedDomains") or []
    if not isinstance(domains, list) or len(domains) > MAX_ALLOWED_DOMAINS:
        raise ValueError("allowedDomains must be a short list")
    normalized_domains = tuple(_normalize_domain(domain) for domain in domains)
    return ResearchTask(query=query, allowed_domains=normalized_domains, budget=ResearchBudget.from_payload(payload))


def validate_findings_payload(payload: dict[str, Any], max_chars: int = MAX_FINDINGS_CHARS) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("findings must be a JSON object")
    encoded = json.dumps(payload, sort_keys=True)
    if len(encoded) > max_chars:
        raise ValueError("findings payload exceeds size budget")
    status = payload.get("status")
    if status not in FINDINGS_STATUSES:
        raise ValueError("findings status is invalid")
    for claim in payload.get("claims", []):
        if not isinstance(claim, dict):
            raise ValueError("claim must be an object")
        text = claim.get("text", "")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("claim text is required")
        hits = detect_prompt_injection(text)
        if hits:
            raise ValueError(f"claim contains possible injection: {', '.join(hits)}")
    for citation in payload.get("citations", []):
        if not isinstance(citation, dict):
            raise ValueError("citation must be an object")
        ensure_public_https_url(citation.get("url", ""), allowed_domains=payload.get("allowedDomains") or None)
        snippet = citation.get("snippet", "")
        if snippet and detect_prompt_injection(str(snippet)):
            raise ValueError("citation snippet contains possible injection")
        if citation.get("sourceTier") not in SOURCE_TIERS:
            raise ValueError("citation sourceTier is invalid")
        retrieved_at = citation.get("retrievedAt")
        if not isinstance(retrieved_at, str) or not retrieved_at.strip():
            raise ValueError("citation retrievedAt is required")
    return payload


def detect_sensitive_content(text: str) -> list[str]:
    matches = []
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            matches.append(pattern.pattern[:28])
    return matches


def detect_prompt_injection(text: str) -> list[str]:
    matches = []
    for pattern in INJECTION_PATTERNS:
        if pattern.search(text):
            matches.append(pattern.pattern[:32])
    return matches


def ensure_public_https_url(url: str, allowed_domains: list[str] | tuple[str, ...] | None = None) -> str:
    if not isinstance(url, str) or not url.strip():
        raise ValueError("url is required")
    parsed = urlparse(url.strip())
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("url must be https with a hostname")
    host = parsed.hostname.lower().strip(".")
    if host in BLOCKED_HOSTS or host.endswith(".local"):
        raise ValueError("url host is not public")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip and (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast):
        raise ValueError("url IP is not public")
    if allowed_domains:
        normalized = tuple(_normalize_domain(domain) for domain in allowed_domains)
        if not any(host == domain or host.endswith(f".{domain}") for domain in normalized):
            raise ValueError("url host is outside the allowed domain set")
    return url.strip()


def classify_source_tier(url: str, allowed_domains: list[str] | tuple[str, ...] | None = None) -> str:
    """Classify the provenance tier of a citation host for downstream weighting."""
    parsed = urlparse(url.strip() if isinstance(url, str) else "")
    host = (parsed.hostname or "").lower().strip(".")
    if not host:
        return "unverified"
    if host.endswith(AUTHORITATIVE_SUFFIXES) or any(
        host == domain or host.endswith(f".{domain}") for domain in AUTHORITATIVE_DOMAINS
    ):
        return "primary"
    if allowed_domains:
        normalized = tuple(_normalize_domain(domain) for domain in allowed_domains)
        if any(host == domain or host.endswith(f".{domain}") for domain in normalized):
            return "reputable"
    return "unverified"


def resolve_effective_allowlist(
    request_domains: list[str] | tuple[str, ...] | None,
    configured_allowlist: list[str] | tuple[str, ...] | None,
) -> tuple[str, ...]:
    """Combine an operator-configured egress ceiling with per-request domains.

    The configured allowlist is a hard ceiling: when it is set the subagent may
    only reach hosts inside it, regardless of what the caller requests. Per-task
    domains can only narrow the ceiling, never widen it. The result is
    fail-closed - when a ceiling is configured it is never empty, so enforcement
    can never silently fall back to "allow any public host".
    """
    configured = tuple(_normalize_domain(domain) for domain in (configured_allowlist or ()))
    requested = tuple(_normalize_domain(domain) for domain in (request_domains or ()))
    if not configured:
        return requested
    narrowed = tuple(
        domain
        for domain in requested
        if any(domain == ceiling or domain.endswith(f".{ceiling}") for ceiling in configured)
    )
    return narrowed or configured


def action_requires_approval(findings: dict[str, Any]) -> bool:
    """Web-influenced findings must be cleared before any privileged tool action."""
    if not isinstance(findings, dict):
        return True
    guardrails = findings.get("guardrails")
    if not isinstance(guardrails, dict):
        return True
    return guardrails.get("actionGate", "requires_approval") != "approved"


def approve_findings_action(findings: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of findings with the action gate cleared for privileged use."""
    if not isinstance(findings, dict):
        raise ValueError("findings must be a JSON object")
    guardrails = dict(findings.get("guardrails") or {})
    guardrails["actionGate"] = "approved"
    updated = dict(findings)
    updated["guardrails"] = guardrails
    return updated


def _normalize_domain(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("domain must be a string")
    domain = value.lower().strip().strip(".")
    if ":" in domain or "/" in domain or len(domain) > 253:
        raise ValueError("domain must be a hostname, not a URL")
    if domain in BLOCKED_HOSTS or domain.endswith(".local"):
        raise ValueError("domain is not public")
    return domain


def _bounded_int(value: Any, minimum: int, maximum: int, name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be an integer")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not minimum <= parsed <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return parsed


def _single_line(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()