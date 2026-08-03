# Testing

Use this skill when designing, changing, running, reviewing, or reporting checks.

## Start with the behavior

Read the [Testing Charter](../../testing/testing-charter.md) in full. State the starting conditions,
action, expected result, and observed result. A successful command counts only when it exercises the
behavior being changed.

Choose checks based on risk:

- use focused unit or integration tests while developing;
- run the repository verification command before completion;
- run assistant evals when prompts, tools, skills, or agent choices change;
- run the real browser journey when user-visible behavior changes; and
- verify the deployed application when Azure behavior or deployment changes.

## Repository verification

Read the checking section of the [local development guide](../guides/local-development.md), then run:

```text
uv run python -m scripts.workbench verify
```

Use `--skip-bicep` only when Azure CLI is unavailable and state that Bicep was not checked.

## Local application and browser testing

Follow the [local development guide](../guides/local-development.md). Use a unique local run ID,
dedicated loopback ports, and dedicated Cosmos database and container names. Start the application
with:

```text
uv run python -m scripts.workbench dev
```

The browser journey calls the configured model and changes isolated demo data, so obtain the user's
approval first. Set the Windows, macOS, or Linux environment values exactly as shown in the guide,
then run:

```text
uv run python -m scripts.workbench eval playwright
```

Inspect the browser result, screenshots, application state, and structured assistant events. Report
the source revision, run ID, local addresses, and evidence location. Do not reuse or stop another
developer's processes.

## Azure testing

Testing an existing deployment does not authorize creating or changing Azure resources. Read the
[deployment guide](../guides/deployment.md), confirm the selected tenant, subscription, instance,
and identity mode, then run the non-deploying verification command:

```text
uv run python -m scripts.workbench deploy verify
```

Run the remote browser journey only for a dedicated demo instance and only with approval to change
its demo records:

```text
uv run python -m scripts.workbench deploy verify --browser
```

Do not run that browser journey against an Entra or shared instance. Deployment requires a separate
approved plan and the guarded apply flow in the deployment guide.

## Report the evidence

State what ran, what passed, what failed, and what was not checked. For browser or Azure checks,
include the target and source revision without exposing secrets, tokens, or full identity claims.
Source inspection is useful evidence, but do not describe runtime behavior as tested when the
application was not run.
