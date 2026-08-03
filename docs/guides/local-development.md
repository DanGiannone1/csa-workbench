# Local development

## Prerequisites

Install:

- Python 3.12 or later
- `uv`
- Node.js and npm
- an Azure OpenAI endpoint and model deployment reachable by the developer
- a separately provided Cosmos DB emulator

Azure CLI with Bicep support is needed for deployment and the optional Bicep portion of local
verification, not to set up or run the app. The repository does not install or configure the Cosmos
emulator.

## Install dependencies

```text
uv run --no-sync python -m scripts.workbench setup
```

This is the same command on Windows, macOS, and Linux. It checks the local tools, creates `.env`
from `.env.example` only when `.env` is absent, and installs the locked root, Python, and frontend
dependencies. It never overwrites an existing `.env`.

The default and deployed assistant runtime is Deep Agents. Repository development installs the
optional Copilot comparison adapter so its compatibility checks can run; the production image uses
the no-development dependency set and does not install the Copilot SDK.

Set `IDENTITY_MODE=demo`, a local `DEMO_PASSWORD`, the Azure OpenAI values, and Cosmos emulator values
in `.env`. Do not commit real secrets. Read `.env.example` for the current variable names.

All demo accounts (`dan`, `ava`, `sam`) sign in with the running `DEMO_PASSWORD`. Nothing
credential-related is stored in the database, so changing the password is just editing `.env`
and restarting the app.

## Start the application

```text
uv run python -m scripts.workbench dev
```

The launcher starts the frontend, API, and assistant runtime as separate processes.

## Run an isolated copy

Use a short run ID, three unused loopback ports, and Cosmos names dedicated to that run. Put values
such as these in `.env`, then run the same `dev` command shown above:

```dotenv
CSA_LOCAL_RUN_ID=demo1
CSA_RUNTIME_PORT=18080
CSA_API_PORT=18000
CSA_FRONTEND_PORT=13000
IDENTITY_MODE=demo
DEMO_PASSWORD=local-only-secret
COSMOS_ENDPOINT=http://localhost:8081
COSMOS_DATABASE=csa_workbench_demo1_local
COSMOS_CONTAINER=appstate_demo1_local
```

Both Cosmos names must contain the run ID and either `demo` or `local`. The endpoint must use
loopback. The launcher creates:

- `.local-runs/demo1/` for runtime files and logs;
- `.mvp-artifacts/demo1/` for local Engagement artifact files; and
- `frontend/.next-local-runs/demo1/` for the frontend build.

The launcher stops only processes that it started.

## Run repository checks

```text
uv run python -m scripts.workbench verify
```

This command checks dependency locks, Python tests, assistant evidence contracts, Waza schemas and readiness,
frontend contracts, lint, the frontend build, Bicep compilation, and whitespace. It cleans its own
temporary files on every platform. If Azure CLI is not installed, use `--skip-bicep`; CI uses that
option and runs the rest on Windows, macOS, and Linux.

Waza v0.38.3 runs natively on all three operating systems with a pinned binary checksum. On Windows,
`uv run python -m scripts.workbench eval waza check --wsl` is available as an explicit fallback if a
developer prefers WSL.

## Run the assistant evaluation

This command calls the configured model and requires a running isolated application and the user's
approval:

PowerShell on Windows:

```powershell
$env:CSA_LOCAL_RUN_ID='demo1'
$env:WORKSPACE='.local-runs/demo1/workspace'
$env:ARTIFACTS_DIR='.mvp-artifacts/demo1'
$env:IDENTITY_MODE='demo'
$env:DEMO_PASSWORD='local-only-secret'
$env:COSMOS_ENDPOINT='http://localhost:8081'
$env:COSMOS_DATABASE='csa_workbench_demo1_local'
$env:COSMOS_CONTAINER='appstate_demo1_local'
$env:MVP_API_URL='http://localhost:18000'
$env:MVP_RAW_TRACE_ROOT='.local-runs/demo1/logs/sdk-events'
$env:MVP_RESET_BEFORE_RUN='1'
uv run python -m scripts.workbench eval mvp
```

Terminal on macOS or Linux:

```bash
export CSA_LOCAL_RUN_ID=demo1
export WORKSPACE=.local-runs/demo1/workspace
export ARTIFACTS_DIR=.mvp-artifacts/demo1
export IDENTITY_MODE=demo
export DEMO_PASSWORD='local-only-secret'
export COSMOS_ENDPOINT='http://localhost:8081'
export COSMOS_DATABASE='csa_workbench_demo1_local'
export COSMOS_CONTAINER='appstate_demo1_local'
export MVP_API_URL='http://localhost:18000'
export MVP_RAW_TRACE_ROOT='.local-runs/demo1/logs/sdk-events'
export MVP_RESET_BEFORE_RUN=1
uv run python -m scripts.workbench eval mvp
```

`MVP_EVAL_SCOPE` may be `all`, `atomic`, or `workflow`; the default is `all`.

## Run the browser journey

This command calls the configured model and changes the isolated demo data. Run it only with the
user's approval after the isolated application is ready:

PowerShell on Windows:

```powershell
$env:CSA_LOCAL_RUN_ID='demo1'
$env:WORKSPACE='.local-runs/demo1/workspace'
$env:ARTIFACTS_DIR='.mvp-artifacts/demo1'
$env:IDENTITY_MODE='demo'
$env:DEMO_PASSWORD='local-only-secret'
$env:COSMOS_ENDPOINT='http://localhost:8081'
$env:COSMOS_DATABASE='csa_workbench_demo1_local'
$env:COSMOS_CONTAINER='appstate_demo1_local'
$env:MVP_APP_URL='http://localhost:13000'
$env:MVP_API_URL='http://localhost:18000'
$env:MVP_RAW_TRACE_ROOT='.local-runs/demo1/logs/sdk-events'
$env:MVP_RESET_BEFORE_RUN='1'
uv run python -m scripts.workbench eval playwright
```

Terminal on macOS or Linux:

```bash
export CSA_LOCAL_RUN_ID=demo1
export WORKSPACE=.local-runs/demo1/workspace
export ARTIFACTS_DIR=.mvp-artifacts/demo1
export IDENTITY_MODE=demo
export DEMO_PASSWORD='local-only-secret'
export COSMOS_ENDPOINT='http://localhost:8081'
export COSMOS_DATABASE='csa_workbench_demo1_local'
export COSMOS_CONTAINER='appstate_demo1_local'
export MVP_APP_URL='http://localhost:13000'
export MVP_API_URL='http://localhost:18000'
export MVP_RAW_TRACE_ROOT='.local-runs/demo1/logs/sdk-events'
export MVP_RESET_BEFORE_RUN=1
uv run python -m scripts.workbench eval playwright
```

The environment variables in the parent shell must match the values used to start the `dev` command.

## Optional Reminder email

Set `ACS_EMAIL_ENDPOINT` and `ACS_SENDER_ADDRESS` to use Azure Communication Services with the
developer's Azure credentials. Demo users send only to `REMINDER_DEMO_EMAIL`. Without these values,
Reminders continue to work in the application without sending email.
