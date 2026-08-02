# CSA Workbench

CSA Workbench is an internal workspace for Cloud Solution Architects. It brings shared customer
Engagements, private tasks and calendar work, and an assistant into one application.

The product is designed to be useful without AI. People can create and update Engagements, manage
their own work, and share Engagements through the web application. The assistant provides another
way to perform supported actions through the same application services.

## What you can do

- Create and share customer Engagements with owner, editor, and viewer roles.
- Track Engagement status, dates, tasks, conventions, and artifacts.
- Manage private Tasks, Calendar events, and Reminders.
- Ask the assistant to read or update supported records and open supported pages.
- Prepare an Engagement meeting brief or run a personal weekly review.

## Main workflow

A CSA creates or opens a customer Engagement, reviews its current status and delivery information,
and shares it with the right team members. They can then ask the assistant to prepare a meeting
brief, make a supported status change, and open the updated Engagement. Private Tasks, Calendar
events, and Reminders remain available only to the signed-in user throughout that work.

## How we test the assistant

Testing follows a four-layer model — unit checks, integration checks, deterministic agent evals
against the running product, and LLM-as-judge review — described in the
[Testing Charter](testing/testing-charter.md). The agent-eval pipeline end to end, including the
Azure AI Foundry integration, is in [testing/agent-evals.md](testing/agent-evals.md).

## Run it locally

Install Python 3.12 or later, `uv`, Node.js and npm, Azure CLI, and a local Cosmos DB emulator. Then:

```bash
cp .env.example .env
npm ci
uv sync
(cd session-container && uv sync)
(cd frontend && npm ci)
uv run dev.py
```

Set the local identity, model, and Cosmos values in `.env` before starting. The
[local development guide](docs/guides/local-development.md) lists the required settings and shows
how to run an isolated copy.

## How it works

```text
Browser -> Next.js frontend -> FastAPI API -> assistant runtime -> Azure OpenAI
                              |
                              +-- Cosmos DB
                              +-- Engagement artifact storage
```

The API and assistant runtime use shared application services for Engagements and personal work.
This keeps authorization, validation, and saved results consistent whether an action starts in the
web application or through the assistant.

## Target repository hierarchy

The repository is moving toward the following approved hierarchy. Until that migration is complete,
some active files remain in their earlier locations; the current development and deployment guides
remain authoritative for commands and paths.

```text
csa-workbench/
|-- backend/
|   |-- api/
|   |   |-- src/
|   |   |   `-- workbench_api/
|   |   |       |-- __init__.py
|   |   |       |-- main.py
|   |   |       |-- artifacts.py
|   |   |       |-- auth.py
|   |   |       |-- identity.py
|   |   |       `-- sessions.py
|   |   |-- Dockerfile
|   |   `-- pyproject.toml
|   |-- assistant/
|   |   |-- src/
|   |   |   `-- workbench_assistant/
|   |   |       |-- __init__.py
|   |   |       |-- main.py
|   |   |       |-- agent.py
|   |   |       |-- deep_agent.py
|   |   |       |-- navigation.py
|   |   |       |-- schemas.py
|   |   |       |-- skill_runtime.py
|   |   |       |-- tracing.py
|   |   |       `-- workload_auth.py
|   |   |-- product-skills/
|   |   |   |-- calendar/
|   |   |   |-- engagement-meeting-prep/
|   |   |   |-- tasks/
|   |   |   `-- weekly-review/
|   |   |-- seed-docs/
|   |   |-- Dockerfile
|   |   `-- pyproject.toml
|   `-- core/
|       |-- src/
|       |   `-- workbench_core/
|       |       |-- __init__.py
|       |       |-- engagements.py
|       |       |-- personal_workspace.py
|       |       |-- persistence.py
|       |       |-- reminders.py
|       |       |-- request_limits.py
|       |       |-- security.py
|       |       |-- telemetry.py
|       |       |-- tool_protocol.py
|       |       `-- upload_policy.py
|       `-- pyproject.toml
|-- frontend/
|   |-- src/
|   |   |-- app/
|   |   |-- components/
|   |   |-- hooks/
|   |   `-- lib/
|   |-- public/
|   |-- Dockerfile
|   |-- package.json
|   `-- tsconfig.json
|-- tests/
|   |-- unit/
|   |   |-- api/
|   |   |-- assistant/
|   |   |-- core/
|   |   `-- frontend/
|   |-- integration/
|   |-- contracts/
|   |-- e2e/
|   `-- evals/
|       |-- cases/
|       |-- rubrics/
|       `-- waza/
|-- docs/
|   |-- product/
|   |-- architecture/
|   |   `-- capabilities/
|   |-- guides/
|   |-- governance/
|   |-- reference-architectures/
|   |-- testing/
|   `-- README.md
|-- infra/
|   |-- bicep/
|   `-- scripts/
|-- scripts/
|   |-- dev.py
|   |-- verify.sh
|   |-- evals/
|   `-- operations/
|-- .claude/
|-- .codex/
|-- .github/
|   `-- workflows/
|-- .dockerignore
|-- .env.example
|-- .gitignore
|-- .python-version
|-- .waza.yaml
|-- AGENTS.md
|-- CLAUDE.md
|-- CONTRIBUTING.md
|-- README.md
|-- package.json
|-- package-lock.json
|-- pyproject.toml
`-- uv.lock
```

The top-level ownership is:

- `backend/` contains the Python API, assistant runtime, and their shared core package.
- `frontend/` contains the Next.js browser application.
- `tests/` contains unit, integration, contract, end-to-end, and evaluation checks.
- `docs/` contains product, architecture, governance, testing, and operational guidance.
- `infra/` contains deployment definitions and infrastructure-specific scripts.
- `scripts/` contains repository development, verification, evaluation, and operational commands.

The frontend communicates with the API over HTTP and server-sent events. The API communicates with
the assistant runtime over HTTP. The API and assistant may import `backend/core`; neither may import
the other application's source directly, and the core package may not import any application.

## Where to go next

- [Understand the product](docs/product/overview.md)
- [Read the current architecture](docs/architecture/README.md)
- [Run it locally](docs/guides/local-development.md)
- [Demonstrate the main workflow](docs/guides/demo.md)
- [Contribute](CONTRIBUTING.md)
- [Deploy an isolated Azure instance](docs/guides/deployment.md)
- [Browse all documentation](docs/README.md)

CSA Workbench is an internal MVP. It does not claim production readiness, external distribution,
or a complete project-management and enterprise-search feature set.
