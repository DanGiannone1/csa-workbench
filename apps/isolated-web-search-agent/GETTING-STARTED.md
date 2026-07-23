# Getting Started — Isolated Web Search Hosted Agent

A step-by-step guide for a brand-new user to run this agent locally, first with
offline mock data and then against the **real public web**.

The agent is a Microsoft Foundry hosted agent. A privileged main agent never reads
raw web content; it delegates research to an isolated read-only subagent running in a
sanitized subprocess, and only validated, size-capped findings cross back.

---

## 1. Prerequisites

Install these once:

- **Python 3.13** — `python --version` should report 3.13.x.
- **Azure Developer CLI (azd)** with the AI agents extension —
  `azd version`. Install from <https://aka.ms/azd-install>.
- **An Azure subscription** with access to a **Microsoft Foundry project** and a
  deployed chat model (for example `gpt-4.1-mini`).
- **Git**, to clone the repository.

Sign in so azd and the Azure SDKs can authenticate:

```powershell
az login
azd auth login
```

---

## 2. Get the code

```powershell
git clone https://github.com/fbabaei_microsoft/azure-ai-agent-foundry.git
cd azure-ai-agent-foundry
```

Everything for this agent lives under `apps/isolated-web-search-agent/`.

---

## 3. Create the virtual environment and install dependencies

Create the venv **inside the service source folder**, where `azd ai agent run`
expects it:

```powershell
Push-Location apps/isolated-web-search-agent/src/isolated-web-search-agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install uv
uv pip install -r requirements-dev.txt
Pop-Location
```

---

## 4. Configure environment variables

Copy the template and open the copy for editing:

```powershell
Copy-Item apps/isolated-web-search-agent/src/isolated-web-search-agent/.env.example `
          apps/isolated-web-search-agent/src/isolated-web-search-agent/.env
```

Fill in the two required values from your Foundry project:

```env
FOUNDRY_PROJECT_ENDPOINT="https://<account>.services.ai.azure.com/api/projects/<project>"
AZURE_AI_MODEL_DEPLOYMENT_NAME="gpt-4.1-mini"
```

Leave `WEB_RESEARCH_MODE="mock"` for now — you will switch it to real web in step 7.

> Never put secrets, API keys, or tokens in `.env`, `azure.yaml`, task payloads, or
> citations. The real-web provider is keyless by design.

### Using a non-Azure-OpenAI catalog model (e.g. MoonshotAI, DeepSeek, Meta)

The Foundry **project** OpenAI surface
(`/api/projects/<project>/openai/v1/`) only exposes **Azure OpenAI** deployments.
If `AZURE_AI_MODEL_DEPLOYMENT_NAME` points at a non-OpenAI catalog deployment
(for example `Kimi-K2.7-Code` from MoonshotAI), the default client returns
`404 DeploymentNotFound`.

To reach those deployments, point the agent at the **account-level**
OpenAI-compatible endpoint by setting `FOUNDRY_OPENAI_BASE_URL`:

```env
FOUNDRY_OPENAI_BASE_URL="https://<account>.services.ai.azure.com/openai/v1/"
```

When this variable is set, the agent uses `OpenAIChatClient` (with Entra ID auth)
against the account gateway, which routes every model format. Leave it unset to
use the default project-scoped `FoundryChatClient` for Azure OpenAI deployments.

> `azd ai agent run` does not load this service's `.env`; it passes the parent
> shell environment to the agent process. For local runs, export the variable in
> your shell **before** starting the server (shown in step 6), or run
> `azd env set FOUNDRY_OPENAI_BASE_URL "https://<account>.services.ai.azure.com/openai/v1/"`.

---

## 5. Run the tests (offline, no Azure needed)

Confirm the isolation contract and providers work before running the agent:

```powershell
python -m pytest apps/isolated-web-search-agent/tests -q
```

All tests should pass. They run fully offline using injected fake providers.

---

## 6. Run locally with mock data

Start the local hosted-agent server (still in `mock` mode):

```powershell
Push-Location apps/isolated-web-search-agent/src/isolated-web-search-agent
.\.venv\Scripts\Activate.ps1
$env:AZURE_DEV_USER_AGENT = "microsoft_foundry_skill"
# Only if using a non-Azure-OpenAI catalog model (see step 4):
$env:FOUNDRY_OPENAI_BASE_URL = "https://<account>.services.ai.azure.com/openai/v1/"
azd ai agent run --no-client
```

From a second terminal, invoke it:

```powershell
$env:AZURE_DEV_USER_AGENT = "microsoft_foundry_skill"
azd ai agent invoke --local "Research current guidance for isolating web search in agentic systems."
```

You will get structured findings (claims + citations) produced from canned data —
proof the isolation path works without touching the network.

Stop the server with `Ctrl+C` when done.

---

## 7. Run against the real public web

Switch the provider to live web. Edit
`apps/isolated-web-search-agent/src/isolated-web-search-agent/.env`:

```env
WEB_RESEARCH_MODE="http"

# Live queries do one search plus several page fetches, so give the subprocess more time
# and keep the fetch count modest for interactive runs:
WEB_RESEARCH_SUBPROCESS_TIMEOUT_SECONDS="90"
WEB_RESEARCH_MAX_FETCHES="4"

# Optional: hard-limit which public hostnames the subagent may reach (comma-separated).
# Leave empty to allow any public HTTPS host.
WEB_RESEARCH_ALLOWED_DOMAINS="learn.microsoft.com,owasp.org"
```

What `http` mode does:

- **Search** uses the keyless DuckDuckGo Instant Answer JSON API (no API key required).
- **Fetch** uses the stdlib-only `HttpWebProvider`, which enforces HTTPS-only, blocks
  non-public hosts, re-checks each host's resolved IP after DNS (post-DNS SSRF defense),
  caps and re-validates redirects, and byte-caps every response.

Restart the server and invoke again:

```powershell
Push-Location apps/isolated-web-search-agent/src/isolated-web-search-agent
.\.venv\Scripts\Activate.ps1
$env:AZURE_DEV_USER_AGENT = "microsoft_foundry_skill"
azd ai agent run --no-client
```

```powershell
$env:AZURE_DEV_USER_AGENT = "microsoft_foundry_skill"
azd ai agent invoke --local "What does OWASP say about prompt injection in LLM apps?"
```

The citations now point at real pages, each tagged with a `sourceTier`
(`primary` / `reputable` / `unverified`) and a `retrievedAt` timestamp.

---

## 8. Understand the results

- `status`:
  - `ok` — usable claims returned.
  - `degraded` — the provider ran but found nothing usable; see `detail`
    (e.g. `no_search_results`, `all_targets_blocked_pre_fetch`).
  - `not_configured` — `WEB_RESEARCH_MODE` is set to an unknown value.
  - `blocked` / `error` — request refused or the subagent failed.
- `guardrails.actionGate` defaults to `requires_approval`: the privileged harness must
  explicitly approve findings before taking any web-influenced action.

---

## 9. Deploy to Azure (optional)

When you are ready to host the agent:

```powershell
Push-Location apps/isolated-web-search-agent
azd provision
azd deploy
Pop-Location
```

Set the same `WEB_RESEARCH_*` variables in your deployment environment. For production,
also enforce an egress allowlist at the network layer as defense in depth.

---

## Troubleshooting

- **`404 DeploymentNotFound` on invoke** — your model is a non-Azure-OpenAI
  catalog deployment. Set `FOUNDRY_OPENAI_BASE_URL` to the account-level
  `/openai/v1/` endpoint and export it in the shell before `azd ai agent run`
  (see step 4). Also confirm no stale agent server is still bound to the port:
  `Get-NetTCPConnection -LocalPort 8088 -State Listen`.
- **`No module named pytest`** — activate the venv first, or install dev deps
  (`uv pip install -r requirements-dev.txt`).
- **Live run times out** — raise `WEB_RESEARCH_SUBPROCESS_TIMEOUT_SECONDS` and/or lower
  `WEB_RESEARCH_MAX_FETCHES`.
- **Empty findings in `http` mode** — the query may have matched no DuckDuckGo instant
  answers, or every candidate page was outside `WEB_RESEARCH_ALLOWED_DOMAINS`. Widen the
  allowlist or rephrase the query.
- **Behind a corporate proxy** — set `HTTPS_PROXY`/`HTTP_PROXY`/`NO_PROXY` (and cert vars
  if needed) in the parent shell; the runtime forwards those non-secret values into the
  subprocess.
