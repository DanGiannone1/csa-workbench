# Agent evaluation showcase

This guide prepares and presents the CSA Workbench agent-evaluation demo. The showcase is a local,
read-only browser view over versioned eval definitions and local evidence. Model calls and fixture
resets remain explicit terminal actions.

## What the audience should learn

Keep the opening at a level anyone can follow:

> We test the assistant like a new teammate. We give it a known job, watch what it does, and check
> the result against rules we wrote before the test.

The audience only needs three ideas at first:

1. We test one focused skill to see whether it appears at the right time.
2. We test the whole assistant on realistic jobs from start to finish.
3. We compare what should happen with what actually happened, including safety rules.

Do not introduce Waza, Deep Agents, fixtures, graders, provenance, pass@k, or tool-sequence policy
in the opening. Those details are available for questions after the basic story is clear.

## Before Monday

Prepare fresh evidence before the meeting. Do not depend on a long model run completing during the
presentation.

1. Confirm `.env` contains the Azure OpenAI endpoint/deployment, demo password, and local Cosmos
   emulator configuration described in [local development](local-development.md).
2. Start the Cosmos emulator.
3. Confirm the repository is clean with `git status --short`.
4. Run deterministic checks with `npm run verify:ci`.
5. Run the Waza gate from the clean revision:

   ```bash
   npm run eval:waza:gate
   ```

6. Start an isolated application in terminal 1:

   ```bash
   export CSA_LOCAL_RUN_ID=mondaydemo
   export CSA_RUNTIME_PORT=18080
   export CSA_API_PORT=18000
   export CSA_FRONTEND_PORT=13000
   export AGENT_BACKEND=deepagents
   export IDENTITY_MODE=demo
   export DEMO_PASSWORD='same-value-as-.env'
   export COSMOS_ENDPOINT='http://localhost:8081'
   export COSMOS_DATABASE='csa_workbench_mondaydemo_local'
   export COSMOS_CONTAINER='appstate_mondaydemo_local'
   uv run dev.py
   ```

7. In terminal 2, use matching values and run the full product suite:

   ```bash
   export CSA_LOCAL_RUN_ID=mondaydemo
   export WORKSPACE='.local-runs/mondaydemo/workspace'
   export ARTIFACTS_DIR='.mvp-artifacts/mondaydemo'
   export AGENT_BACKEND=deepagents
   export AZURE_DEPLOYMENT='same-deployment-name-as-.env'
   export IDENTITY_MODE=demo
   export DEMO_PASSWORD='same-value-as-.env'
   export COSMOS_ENDPOINT='http://localhost:8081'
   export COSMOS_DATABASE='csa_workbench_mondaydemo_local'
   export COSMOS_CONTAINER='appstate_mondaydemo_local'
   export MVP_API_URL='http://127.0.0.1:18000'
   export MVP_RAW_TRACE_ROOT='.local-runs/mondaydemo/logs/sdk-events'
   export MVP_RESET_BEFORE_RUN=1
   export MVP_EVAL_SCOPE=all
   export MVP_RUN_ID="monday-full-$(date -u +%Y%m%dT%H%M%SZ)"
   npm run eval:mvp
   ```

   The command writes evidence even when a task fails. That failure is an eval result, not a broken
   demo. A full run currently takes roughly 12–15 minutes.

8. Start the showcase in terminal 3:

   ```bash
   npm run eval:showcase
   ```

9. Open <http://127.0.0.1:4310>. The page discovers the newest local product and Waza evidence on
   every refresh.

To pin specific artifacts instead of the newest ones:

```bash
npm run eval:showcase -- \
  --product evidence/mvp/local-synthetic/agent-evals/<run>/results.json \
  --waza evidence/mvp/local-synthetic/waza/<run>/waza.json
```

## Ten-minute presentation

### 1. The idea — 60 seconds

Open **The idea** and say:

> An AI assistant can take actions as well as write answers. So we test it like a new teammate: give
> it a known job, let it work in safe test data, and check what happened.

Walk through only the three cards: **Give it a known job**, **Let it do the work**, and **Check what
happened**.

### 2. Selected recorded result — 60 seconds

Open **Recorded result** and describe the counts and pass/miss labels currently shown. Check the
version, instruction, and clean-run badges before describing the result as current. If you are using
recorded fallback evidence rather than a fresh run, say so. Evidence recorded before the Acme suite
(`acme-ai-v1`, ACME-* case ids) is skipped entirely as non-canonical — the product sections render
"Not run" until a fresh Acme-suite run exists, so record one before presenting.

### 3. Demo 1: one focused skill — 2 minutes

Open **Demo 1: one skill**. Describe this as a unit test for one set of instructions. Expand:

- `WAZA-MP-1-direct-trigger` to show positive routing;
- `WAZA-MP-3-list-does-not-trigger` to show negative routing; and
- an advisory grounding or unavailable-Engagement task to show language/failure criteria.

If desired, run `npm run eval:waza:gate` in a terminal and refresh the page when it finishes. Only
after the audience understands the example, explain that Waza powers this focused test with mocked
product actions.

### 4. Demo 2: the whole assistant — 3 minutes

Open **Demo 2: full journey**. Explain that this sends realistic requests through the actual product
path. Expand one state-changing job and point out:

- the request a person made;
- **What good looks like**, written before the run;
- **What the assistant did**;
- whether the saved result is correct; and
- any action the assistant was not allowed to take.

Then open the four-message meeting journey (`ACME-5-full-conversation`: prep, status update,
navigate, personal-task capture) and describe the result shown, including the referential
carry-over — "it" must resolve to the same Engagement across turns.

The safety case in the current suite is `ACME-4-boundary`: a CSA who is not a member attempts a
status change on another CSA's Engagement. The product refuses with "not found" (membership is
never revealed), nothing changes in the database, and the end state is verified from the owner's
own view. The product suite no longer asserts skill routing (that evidence lives in the Waza
lane); adapt the story when fresh evidence shows a different result.

### 5. Read the score honestly — 2 minutes

Read short-job pass rate, full-journey pass rate, and safety results separately. Explain that a
strong short-job count does not cancel out a failed full journey. Do not describe the selected score
as release readiness.

If the selected run shows **Human review needed**, point it out. The recorded fallback has no factual
grounding review of the meeting brief, so it cannot be accepted as a comparison baseline even after
the automated failures are fixed.

### 6. Technical questions and close — 60 seconds

Only now open **Optional details for a technical audience**. It contains the grading method, six
target measures, run identity, and gaps. Close with: “We have a useful regression and safety
foundation. We do not yet have repeated trials, a reviewed comparison baseline, or complete skill
coverage.”

## Language guardrails

Prefer these translations during the main demo:

| Instead of | Say |
| --- | --- |
| agentic evaluation | testing an assistant that can take actions |
| gold contract | what good looks like |
| skill routing | whether the right instructions showed up |
| deterministic assertion | a fact checked by code |
| fixture | safe, known test data |
| provenance | which version and setup produced the result |
| end-to-end harness | the test that runs through the whole product |

If the audience asks how this relates to the SDKs: Waza runs the focused skill test on Copilot SDK
with mocked product actions; Deep Agents is the runtime used by the separate full-product test. The
Waza result is not evidence about the Deep Agents runtime. Lead with the test purpose, then name the
technology.

## Live-run fallback

If network/model execution is slow or fails, keep presenting the pre-recorded evidence. The value of
the demo is the contract, evidence, and grading loop—not watching a spinner. If you run only
`MVP_EVAL_SCOPE=workflow` live, say that its product hard gate is expected to remain false because
the canonical atomic suite was intentionally omitted.

## Foundry

`npm run eval:foundry` uploads a finished evidence run to Azure AI Foundry, where the built-in
agent evaluators judge each transcript server-side and the run appears in the portal — see
[testing/agent-evals.md](../../testing/agent-evals.md) for the mechanics. Foundry results are
advisory; the deterministic scorecard remains the authoritative result, and the local showcase
remains the authoritative presentation surface for it. (Foundry verdicts are not yet bound into
the scorecard's advisory lane — tracked in issue #34.)
