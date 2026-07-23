# Isolated Web Search Hosted Agent

This project implements the architecture in `C:\Users\fbabaei\Downloads\isolated-web-search-architecture.html` as a runnable Microsoft Foundry hosted-agent scaffold.

## What It Implements

- A privileged **main agent harness** exposed as a Foundry hosted agent.
- An isolated **web research subagent** launched as a subprocess with a sanitized environment.
- A strict downward `ResearchTask` contract that minimizes what crosses to the web-facing side.
- A strict upward `ResearchFindings` contract with citations, size limits, provenance, and prompt-injection scanning.
- Budget controls for iterations, fetches, returned characters, and subprocess runtime.
- SSRF-oriented URL validation for citations and future fetch providers.
- Dependency-free contract and subagent tests for fast local validation.

The design invariant is: the model that reads the web holds no privileged tools, and the model that holds privileged tools never reads raw web content.

> New here? Follow the step-by-step [Getting Started guide](GETTING-STARTED.md) to run
> the agent locally with mock data and then against the real public web.

## Project Layout

```text
apps/isolated-web-search-agent/
  azure.yaml
  AGENTS.md
  README.md
  .vscode/
  src/isolated-web-search-agent/
    main.py
    isolation_contracts.py
    isolation_runtime.py
    web_research.py
    http_web_provider.py
    web_subagent_worker.py
  tests/
```

## Configure

Copy the environment template after provisioning or when binding to an existing Foundry project:

```powershell
Copy-Item src/isolated-web-search-agent/.env.example src/isolated-web-search-agent/.env
```

Required values for local hosted-agent runtime:

```env
FOUNDRY_PROJECT_ENDPOINT="https://<account>.services.ai.azure.com/api/projects/<project>"
AZURE_AI_MODEL_DEPLOYMENT_NAME="gpt-4.1-mini"
WEB_RESEARCH_MODE="mock"
```

Provider modes (`WEB_RESEARCH_MODE`):

- `mock` (default) — returns canned findings with no network calls, so you can exercise
  the isolation path offline.
- `http` (also `live`/`real`/`web`) — hits the **real public web**. Search uses the
  keyless [DuckDuckGo Instant Answer JSON API](https://duckduckgo.com/api) (no API key,
  so no credentials ever enter the sanitized subprocess), and page fetches use the
  stdlib-only, SSRF-hardened `HttpWebProvider` in
  [http_web_provider.py](src/isolated-web-search-agent/http_web_provider.py).

`http` mode adds a few optional tuning knobs (safe defaults shown):
`WEB_RESEARCH_HTTP_TIMEOUT_SECONDS="15"`, `WEB_RESEARCH_MAX_REDIRECTS="3"`,
`WEB_RESEARCH_MAX_BYTES="200000"`, and `WEB_RESEARCH_USER_AGENT`. Because a live query
does one search plus several page fetches, raise `WEB_RESEARCH_SUBPROCESS_TIMEOUT_SECONDS`
(e.g. `90`) and keep `WEB_RESEARCH_MAX_FETCHES` modest (e.g. `4`) for interactive runs.

## Run Tests

```powershell
python -m pytest apps/isolated-web-search-agent/tests -q
```

## Run Locally

Create the virtual environment inside the service source folder, where `azd ai agent run` expects it:

```powershell
Push-Location apps/isolated-web-search-agent/src/isolated-web-search-agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install uv
uv pip install -r requirements-dev.txt
Pop-Location
```

Start the local hosted-agent server:

```powershell
$env:AZURE_DEV_USER_AGENT = "microsoft_foundry_skill"
azd ai agent run --no-client
```

Invoke locally from another terminal:

```powershell
$env:AZURE_DEV_USER_AGENT = "microsoft_foundry_skill"
azd ai agent invoke --local "Research current guidance for isolating web search in agentic systems."
```

## Deployment Notes

- Use `azd provision` and `azd deploy` from this folder when you are ready to create or update the hosted agent.
- Do not put secrets in `.env`, `azure.yaml`, task payloads, or citations.
- The subagent validates every fetch target with `ensure_public_https_url` before retrieving it, so non-public hosts (loopback, link-local `169.254.169.254`, private ranges, `.local`) and out-of-allowlist domains are never fetched. In `http` mode the `HttpWebProvider` adds a **post-DNS SSRF re-check** (it resolves each host and rejects any private/loopback/link-local/reserved/multicast address), caps and re-validates redirects, byte-caps responses, and fails closed (returns empty text) on any violation. A production deployment should still enforce egress allowlists at the network layer as defense in depth.
- `http` mode makes no authenticated calls: the DuckDuckGo Instant Answer search API is keyless, so no credentials cross into the sanitized subprocess. If you run behind a proxy, the runtime forwards only non-secret network config (`HTTPS_PROXY`, `HTTP_PROXY`, `NO_PROXY`, `SSL_CERT_FILE`, `SSL_CERT_DIR`, `REQUESTS_CA_BUNDLE`) and the `WEB_RESEARCH_*` tuning vars into the subprocess; all other environment variables (including secrets) remain stripped.
- Set `WEB_RESEARCH_ALLOWED_DOMAINS` (comma-separated hostnames) to pin an operator egress ceiling. When set, `resolve_effective_allowlist` treats it as a hard boundary: per-request `allowed_domains` can only narrow it, never reach hosts outside it, and it is fail-closed (never falls back to "allow any public host"). Leave it empty to allow any public HTTPS host.
- Findings carry an `actionGate` guardrail that defaults to `requires_approval`. The privileged harness must clear it with `approve_findings_action` (checked via `action_requires_approval`) before any web-influenced privileged tool action.
- Findings `status` distinguishes outcomes: `ok` (usable claims returned), `degraded` (the provider ran but produced no usable claims — see the `detail` reason such as `no_search_results` or `all_targets_blocked_pre_fetch`), `not_configured` (no live provider available), `blocked`, and `error`.
- Each citation carries provenance: `sourceTier` (`primary`, `reputable`, or `unverified`) and a `retrievedAt` ISO-8601 UTC timestamp, so the harness can weight and age-check sources.
