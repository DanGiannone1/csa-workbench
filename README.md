# CSA Workbench

CSA Workbench is an internal workspace for Cloud Solution Architects. It brings shared customer
Engagements, private tasks and calendar work, and an assistant into one application.

The product is designed to be useful without AI. People can create and update Engagements, manage
their own work, and share Engagements through the web application. The assistant provides another
way to perform supported actions through the same application services.

## What you can do

- Create and share customer Engagements with owner, editor, and viewer roles.
- Keep the full delivery record on each Engagement: a status that must state its reason
  when not green, a dated "where it stands" summary, the business value, objectives,
  key dates, customer contacts, and a timeline of meetings, decisions, risks, and
  notes — entries always name who added them and where they came from, and are never
  edited or deleted. Documents are grouped as raw uploads (bronze), working drafts
  (silver), and curated versions someone deliberately promoted (gold).
- Manage private Tasks, Calendar events, and Reminders.
- Open a session to a short ranked list of what needs attention today, built from the
  record — each item opens the matching page.
- Ask the assistant to read or update supported records and open supported pages. The
  assistant uses the same permission checks as the web application, and the chat shows
  what it actually did — the actions it took and their recorded results.
- Prepare an Engagement meeting brief or run a personal weekly review.

## Main workflow

A CSA creates or opens a customer Engagement, reviews its current status and delivery information,
and shares it with the right team members. They can then ask the assistant to prepare a meeting
brief, make a supported status change, and open the updated Engagement. Private Tasks, Calendar
events, and Reminders remain available only to the signed-in user throughout that work.

## How we test the assistant

Testing follows a four-layer model — unit checks, integration checks, scripted agent
evaluations against the running product, and model-as-judge review — described in the
[Testing Charter](testing/testing-charter.md). The full evaluation pipeline — the expected
outcome written down for each scenario, a database reset before every case, captured evidence,
and the scorecard with its Azure AI Foundry review step — is in
[testing/agent-evals.md](testing/agent-evals.md); its **Running it** section is a copy-paste
guide with the exact settings, the output a passing run prints, and what each error message
means. Every run leaves a complete evidence record, and
[docs/guides/eval-showcase.md](docs/guides/eval-showcase.md) turns results into a presentation.

## Design system

The visual system lives in [design-system/](design-system/README.md): a single stylesheet of
named design values (`src/tokens.css`), a small set of shared React components in
`frontend/src/components/ui/`, and a test (`tests/design_system.test.mjs`) that keeps
hard-coded colors, gradients, and one-off styles out of production code. The original design
prototype is preserved read-only under `design-system/reference/` as the traceable source of
the product's look and interaction patterns.

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
|-- design-system/     production design values and the read-only design reference
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
