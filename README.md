# CSA Workbench

CSA Workbench is an internal workspace for Cloud Solution Architects. It brings shared customer
Engagements, private tasks and calendar work, and an assistant into one application.

The product is designed to be useful without AI. People can create and update Engagements, manage
their own work, and share Engagements through the web application. The assistant provides another
way to perform supported actions through the same application services.

## What you can do

- Create and share customer Engagements with owner, editor, and viewer roles.
- Keep the full delivery record on each Engagement: status with its stated reason, a
  "where it stands" summary, business value, objectives, key dates, customer contacts,
  an append-only typed timeline (meetings, decisions, risks, notes), and documents in
  bronze / silver / gold tiers with explicit promotion.
- Manage private Tasks, Calendar events, and Reminders.
- Open a session to a ranked brief of what needs attention today, computed from the
  record — with items that route straight into it.
- Ask the assistant to read or update supported records and open supported pages; every
  assistant action goes through the same authorized application services as the UI, and
  every visible chat state is driven by a typed AG-UI event.
- Prepare an Engagement meeting brief or run a personal weekly review.

## Main workflow

A CSA creates or opens a customer Engagement, reviews its current status and delivery information,
and shares it with the right team members. They can then ask the assistant to prepare a meeting
brief, make a supported status change, and open the updated Engagement. Private Tasks, Calendar
events, and Reminders remain available only to the signed-in user throughout that work.

## How we test the assistant

Testing follows a four-layer model — unit checks, integration checks, deterministic agent evals
against the running product, and LLM-as-judge review — described in the
[Testing Charter](testing/testing-charter.md). The agent-eval pipeline end to end — gold
contracts, per-case fixture resets, evidence capture, the scorecard, and the Azure AI Foundry
integration — is in [testing/agent-evals.md](testing/agent-evals.md); its **Running it** section
is a copy-paste quickstart with the exact environment, the expected output, and the common
failure messages. Every eval run leaves a signed evidence bundle, and
[docs/guides/eval-showcase.md](docs/guides/eval-showcase.md) renders results for presentation.

## Design system

The visual system lives in [design-system/](design-system/README.md): one production token
source (`src/tokens.css`), semantic React primitives in `frontend/src/components/ui/`, and a
test (`tests/design_system.test.mjs`) that keeps hard-coded colors, gradients, and ad hoc
styles out of production code. The original design prototype is preserved read-only under
`design-system/reference/` as the traceable source of the product's look and interaction
patterns.

## Run it locally

Install Python 3.12 or later, `uv`, Node.js and npm, and a local Cosmos DB emulator. Then run the
same two commands from PowerShell, Terminal, or any other shell on Windows, macOS, or Linux:

```bash
uv run --no-sync python -m scripts.workbench setup
uv run python -m scripts.workbench dev
```

Setup creates `.env` only when it is missing and never overwrites an existing file. Set the local
identity, model, and Cosmos values there before starting. Azure CLI is needed only for deployment
and the optional local Bicep check. The
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

## Repository map

```text
csa-workbench/
|-- backend/
|   |-- api/
|   |   |-- src/workbench_api/
|   |   |-- Dockerfile
|   |   `-- pyproject.toml
|   |-- assistant/
|   |   |-- src/workbench_assistant/
|   |   |-- product-skills/
|   |   |-- seed-docs/
|   |   |-- Dockerfile
|   |   `-- pyproject.toml
|   `-- core/
|       |-- src/workbench_core/
|       `-- pyproject.toml
|-- frontend/          Next.js application
|-- design-system/     production tokens and quarantined reference assets
|-- tests/             automated checks and evaluation data
|-- testing/           testing and evaluation guidance
|-- docs/              product, architecture, and contributor documentation
|-- infra/             Azure infrastructure and guarded deployment
|-- scripts/           setup, local run, verification, eval, and support commands
|-- .claude/           Claude-native developer configuration
|-- .codex/            Codex-native developer configuration
`-- .github/           GitHub Actions and Copilot-native configuration
```

Each Python component is an explicit workspace package. The API and assistant use
`workbench_core`; they do not import one another. The frontend talks to the API over HTTP and
server-sent events, and the API talks to the assistant runtime over HTTP.

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
