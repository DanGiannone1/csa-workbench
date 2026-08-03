# Agent evaluation: how it runs

New to evaluations? Begin with [Input prompt + Expected output](../tests/evals/README.md). This
page is the engineering reference for the live product runner. For the separate skill laboratory,
use [the Waza guide](waza-skill-evals.md).

This guide explains the agent-eval pipeline end to end: where the scenarios live, how a run
executes against the real product, what the deterministic grader checks, and how the same
evidence is scored by Azure AI Foundry's evaluators as an advisory second opinion.

The one-line mental model: **write down what good looks like before the run; drive the real
product; grade the facts with code (gate); grade the language with LLM evaluators (advise).**

This guide covers layers 3 and 4 of the [four-layer testing model](testing-charter.md); current status and
known gaps are tracked there too.

The whole flow in one picture:

```mermaid
flowchart LR
    A["Gold-standard prompts<br/>tests/evals/"] --> B["Reset to known test data<br/>before every scenario"]
    B --> C["The real product<br/>sign in, send the prompt"]
    C --> D["Transcript saved<br/>tool calls · answers · DB before/after"]
    D --> E["Deterministic checks<br/>code grades the facts — the gate"]
    D --> F["Clean + reshape<br/>the transcript"]
    E -. "pass/fail rides along" .-> F
    F --> G["Foundry evaluators<br/>LLM judges grade the language — advisory"]
```

Five parts make this work, and the sections below walk them in order: gold-standard scenarios
that say what good looks like; test identities to sign in with; a driver that runs the prompts
through the real product and saves the evidence; deterministic checks that grade it; and the
Foundry upload for a judged second opinion.

One naming note before you read the files: this guide says **scenario** throughout, while the
code and JSON say *case* (`mvp-cases.json`, `atomicCaseIds`, `evaluateCase`, `MVP_EVAL_SCOPE=atomic`)
— same thing. Inside a scenario, the `scenario` field is just its title.

## The pieces

| Piece | Where | What it is |
|---|---|---|
| Gold-standard scenarios | `tests/evals/mvp-cases.json`, `tests/evals/mvp-workflows.json` | 8 scenarios — 7 single prompts and 1 four-turn conversation. Each states the prompt(s) a user would type, who is signed in, the expected tool calls and arguments (exact or a declared subset), forbidden actions, and the expected database end state. Single prompts isolate one behavior each; the conversation proves context carries across turns ("Open it." must still mean the same Engagement) |
| Official suite list | `scripts/mvp_eval_manifest.mjs` | The frozen list of scenario ids the scorecard accepts, and which of them pass or fail as a whole (the safety scenario) |
| Test identities | `backend/api/src/workbench_api/auth_users.py`, seeded in `backend/core/src/workbench_core/appdb.py` | Three demo accounts (dan / ava / sam) sharing one demo password; every scenario names which one runs the prompt |
| Known test data | `backend/core/src/workbench_core/appdb.py` (`_seed_engagements`), reset via `scripts/reset_demo_state.py` | The demo data every run starts from (version `acme-ai-v1`): actors dan/ava/sam and three engagements around the "Acme Internal AI Chatbot" story |
| Driver | `scripts/mvp_agent_eval.mjs` | Runs the suite against the live app and writes evidence |
| Grader | `scripts/mvp_evidence.mjs` | `evaluateCase` / `evaluateWorkflow`: the deterministic checks |
| Scorecard | `scripts/mvp_scorecard.mjs` (+ `mvp_scorecard_history.mjs`) | Aggregates evidence into the product hard gate, Waza lane, and advisory-judge lane |
| Foundry upload | `scripts/foundry_evidence_rows.py`, `scripts/foundry_eval_upload.py` | Converts evidence to Foundry's agent-message schema and scores it server-side with the built-in agent evaluators |
| Judge questions | `tests/evals/judge-rubrics.json`, checked by `scripts/mvp_judge.mjs` | The other half of layer 4: per-scenario questions a human answers by hand today (accuracy, leakage, tone), separate from the Foundry lane |
| Skill laboratory | `python -m scripts.workbench eval waza`, `tests/evals/waza/**` | Separate lane: skills tested in isolation with mocked product actions; see [the Waza guide](waza-skill-evals.md) |

## Test identities

Every scenario runs as a real signed-in user, not a mocked one. In demo identity mode the app
seeds three test accounts — dan, ava, sam — who share one demo password (`DEMO_PASSWORD`), and
the driver logs each one in through the product's own `POST /auth/login`, so evals exercise the
same sign-in path a person uses. Every scenario names its actor, and the boundary scenario needs
two: dan asks to flag an Engagement he is not a member of, and the untouched end state is then
verified from sam's own signed-in view, since sam is the only member of that Engagement.

Evals only ever run against an isolated instance with this seeded data — production runs Entra
and has no demo mode. An app without an in-app demo mode does the same thing with dedicated test
users in an isolated test deployment; that's the documented test-tenant procedure cited in the
design position below. Sign-in itself is the swappable part — a local copy could accept a
test-mode header naming the user instead of a login. The seeded users aren't swappable: who is
asking scopes what the assistant sees, and the boundary scenario needs two users the app
enforces permissions between.

## What happens on `npm run eval:mvp`, step by step

1. **Preconditions.** The driver refuses to run without `MVP_RESET_BEFORE_RUN=1` and
   `DEMO_PASSWORD`, refuses non-loopback API targets, and refuses a dirty git worktree —
   evidence is only produced from a known revision.
2. **Test-data reset — before every scenario, not once per run.** `reset_demo_state.py` is
   guarded so it can only ever point at a loopback Cosmos emulator with demo/local-named
   database and container. It deletes everything, reseeds through the same code path the
   product uses, and returns the data version plus a SHA-256 fingerprint that the driver
   verifies never drifts mid-run.
3. **Real sign-in, real session.** For each scenario the driver logs in as the contract's
   actor (`POST /auth/login`), opens a session (`POST /sessions`), and — for boundary cases —
   opens a second session as an `observerActor` so the end state is verified from another
   user's authoritative view.
4. **State snapshot → the turn → state snapshot.** App state is read through the product's own
   endpoint (`GET /sessions/{id}/app/state`) before and after. The prompt goes to
   `POST /sessions/{id}/messages`; the response is the live SSE event stream (tool call
   start/args/result/end, text deltas, navigation, terminal event).
5. **Second evidence source.** The driver also fetches the server-side raw SDK trace
   (`logs/sdk-events/<session>.jsonl`) and keeps only the records for this run id. Client
   stream and server trace must corroborate.
6. **Grading.** `evaluateCase` computes every check, then credits only the ones the contract
   declares (`applicablePrimaryCheckNames`). Most scenarios earn credit per check; the safety
   scenario passes or fails as a whole. The conversation re-grades each turn the same way,
   plus conversation-wide checks.
7. **Evidence out.** Everything — prompts, events, raw traces, before/after state, verdicts —
   is written to `evidence/mvp/local-synthetic/agent-evals/<run>/results.json`, with a
   scorecard beside it. The process exits non-zero if anything failed.

## What the deterministic checks verify

Six families (about three dozen named checks in `mvp_evidence.mjs`):

- **Protocol** — the event stream is well-formed: one terminal event, complete tool-call
  lifecycles, result operations matching their tools, navigation bound to a real result.
- **Tool calls** — the expected call happened with the expected arguments (exact `args`, or an
  `argsInclude` subset when only some fields matter); required tools present; forbidden tools
  absent; no write or navigation targeted any engagement other than the declared one. Reads are deliberately unbounded: any path that produces the same
  verified end state passes (τ²-bench's rule), so contracts never degrade into tool-sequence
  choreography.
- **Database end state** — read back through the product API afterward: the named engagement
  has the expected status/note; nothing else changed (single-domain invariants
  `onlyEngagementMayChange` / `onlyPersonalAggregateMayChange`, or the joint
  `onlyEngagementAndPersonalAggregateMayChange` when one prompt legitimately writes an
  engagement *and* a personal record); safety cases prove no write was committed.
- **Grounding** — where a scenario declares it (today, the meeting-prep read), the tool output
  the model saw is re-rendered independently from the pre-turn database and must match: the
  brief cannot rest on invented facts.
- **Corroboration** — every client-visible tool result must match the server-side trace record.
- **Conversation integrity** (the multi-turn scenario) — one session throughout, each turn starting from the
  previous turn's exact end state, expected turn count, expected final engagement state.

Assistant wording is deliberately **recorded but never scored** here — free-form prose cannot
be pass/failed deterministically. The checks confirm an answer exists and that what the model
was told is true; judging the answer's quality is the advisory lane's job.

**Read-only features** are graded by the same families, minus the end-state one — there is
nothing to assert about a database that shouldn't have changed. `ACME-3-meeting-prep` and
`ACME-6-portfolio-triage` are the template: code gates the actions (the right records were read,
nothing was written, nothing else was touched) and grounding gates honesty, while whether the
summary was *useful* goes to the judges.

**Scenarios whose right answer is to refuse** get graded twice, and the better result counts.
`ACME-4-boundary` can correctly come out two ways: the assistant refuses outright without
touching a tool, or it tries a read, gets "not found", and stops. The contract declares both as
acceptable, so a correct refusal is never punished for taking one shape rather than the other.

## Shipping the transcript to Foundry

Layer 4 is three mechanical steps:

1. **Save the transcript.** The layer-3 run already recorded everything: the prompt, every tool
   call with arguments and results, and the answer text (in `results.json`).
2. **Convert to Foundry's expected shape** (`scripts/foundry_evidence_rows.py`). Each scenario
   (or conversation turn) becomes one row:

   ```json
   {
     "item_id": "ACME-2-update-status",
     "harness_pass": true,
     "user_request": "Acme's data-privacy review just slipped to August 12. Put the chatbot engagement at Yellow, reason '…'.",
     "agent_messages": [
       {"role": "assistant", "content": [{"type": "tool_call", "tool_call_id": "…",
         "name": "set_engagement_status",
         "arguments": {"engagement_id": "eng-acme-ai-chatbot", "status": "yellow", "note": "…"}}]},
       {"role": "tool", "tool_call_id": "…", "content": [{"type": "tool_result",
         "tool_result": {"status": "committed", "operation": "update", "…": "…"}}]},
       {"role": "assistant", "content": [{"type": "text", "text": "The engagement is now Yellow…"}]}
     ],
     "tool_defs": ["…every product tool's JSON schema, generated from mvp_tool_schemas.py…"],
     "expected_actions": ["set_engagement_status"]
   }
   ```

   The reconstruction keys tool calls by `tool_call_id` (calls can interleave in the stream),
   keeps result payloads (several evaluators judge whether the agent *used* what tools
   returned), and refuses evidence whose ids aren't on the suite list.
3. **Send** (`scripts/foundry_eval_upload.py`): two API calls — `evals.create` names the built-in
   evaluators and the judge deployment; `evals.runs.create` hands over the rows. Judging runs
   server-side in Foundry; the run appears in the portal with per-row scores and reasoning.

`npm run eval:foundry` performs steps 2–3 against a finished evidence file, with tool
definitions generated from `backend/assistant/src/workbench_assistant/mvp_tool_schemas.py` and ground-truth tool
sequences derived from each gold contract, and submits to the Foundry evals API. Microsoft's built-in agent evaluators —
intent resolution, tool-call accuracy, task adherence, task completion, tool selection/input
accuracy/output utilization/call success, quality, customer satisfaction, and the
deterministic task-navigation-efficiency — run **server-side** with an LLM judge and appear in
the Foundry portal. Each row carries the deterministic `harness_pass` verdict so the two
gradings can be compared per scenario.

Required environment: `MVP_RESULTS` (path to `results.json`), `FOUNDRY_PROJECT_ENDPOINT`,
`FOUNDRY_JUDGE_DEPLOYMENT` (must differ from the model under test; the script enforces this),
optional `FOUNDRY_EVAL_GROUP_ID` to add runs to an existing group. Output lands as
`foundry-run.json` beside the evidence, including the portal `report_url`.

Two limits worth knowing when reading the portal. The scenarios whose correct answer is *do
nothing* (the boundary case, the vague ask) declare no expected tool calls, so their rows carry
an empty `expected_actions` and the tool-oriented evaluators have nothing meaningful to score —
their real contract lives in the deterministic checks. And the one deterministic evaluator,
task navigation efficiency, is configured order-insensitively, because our own contracts grade
outcomes rather than tool order.

Foundry results are **advisory by design**: LLM judges are valuable for language quality and
task-level second opinions, but they are policy-blind and judge-model-sensitive. Where a judge
disagrees with a deterministic check, the deterministic check is authoritative.

## Design position

- **We grade the final database state in code, like the main agent benchmarks do.**
  [τ-bench](https://arxiv.org/abs/2406.12045) and τ²-bench hash the post-run database against a
  gold state — no LLM judge in the reward path — and
  [AgentBench's DB track](https://arxiv.org/abs/2308.03688) and
  [WebArena](https://arxiv.org/abs/2307.13854) verify final environment state the same way.
- **Contracts assert outcomes and safety envelopes, not tool paths.**
  [τ²-bench's evaluation docs](https://github.com/sierra-research/tau2-bench/blob/main/docs/evaluation.md)
  state the rule we follow: "any sequence of tool calls that produces an equivalent DB end state
  passes." [Anthropic's eval guidance](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
  calls checking "a sequence of tool calls in the right order" "too rigid" and "overly brittle."
- **Demo identities in an isolated instance follow Microsoft's own testing procedure** — a
  [separate test environment](https://learn.microsoft.com/en-us/entra/identity-platform/test-setup-environment)
  with [dedicated test users](https://learn.microsoft.com/en-us/entra/identity-platform/test-automate-integration-testing),
  because interactive sign-in with MFA can't be scripted against a production tenant.
  [Playwright's auth guidance](https://playwright.dev/docs/auth) uses the same pattern:
  pre-created test accounts.
- **Foundry's [built-in agent evaluators](https://learn.microsoft.com/en-us/azure/foundry/concepts/evaluation-evaluators/agent-evaluators)
  judge transcripts only** — they have no concept of environment state — so outcome checking is
  custom code by design. That custom code is our deterministic layer.
- **The known weak spot of this approach is authoring errors in the gold scenarios.**
  [τ²-bench-verified](https://github.com/amazon-agi/tau2-bench-verified) found reference
  solutions that violated the domain's own policies. Our scenarios get independent review like
  any other code.

## The one-command demo

To watch a single prompt travel through both layers — deterministic verdict printed fact by
fact, then the same transcript judged in Foundry:

```bash
npm run eval:demo ACME-2-update-status     # any single-prompt scenario id; app must be running
```

It prints the agent's tool calls with arguments, the database before/after from authoritative
reads, every credited check ✓/✗, then ships the transcript to Foundry and prints the portal
link (set `FOUNDRY_PROJECT_ENDPOINT` and `FOUNDRY_JUDGE_DEPLOYMENT`). Demo runs land in
`.local-runs/eval-demo/` and are not evidence — the provenance gates of `eval:mvp` are skipped.

## Running it

Four preconditions, checked before anything runs — each is a deliberate evidence guarantee:

1. **A committed worktree.** The driver records the source revision in the evidence and refuses
   a dirty tree (`live evidence requires a clean Git worktree`). Commit first, then run.
2. **A reachable model.** `.env` needs a real `AZURE_ENDPOINT`/`AZURE_DEPLOYMENT` your machine
   can call. A private-endpoint-only account fails mid-turn with
   `403 Public access is disabled` — pick an account with public network access or run from a
   network that can reach it.
3. **An explicit fixture reset.** `MVP_RESET_BEFORE_RUN=1` acknowledges that every case starts
   from a wiped, re-seeded demo database.
4. **The raw trace location.** The app writes model-visible tool evidence under its run
   directory; `MVP_RAW_TRACE_ROOT` must point at that exact `sdk-events` folder or the driver
   stops with `ENOENT … logs`.

Worked end-to-end example using an isolated local run named `demo1` (bash; PowerShell is the
same values via `$env:`). The same variables drive the app, the reset guard, and the eval —
export them once in each terminal:

```bash
# Shared isolated-run values (both terminals).
export CSA_LOCAL_RUN_ID=demo1 CSA_RUNTIME_PORT=18080 CSA_API_PORT=18000 CSA_FRONTEND_PORT=13000
export COSMOS_DATABASE=csa_workbench_demo1_local COSMOS_CONTAINER=appstate_demo1_local
export ARTIFACTS_DIR=.mvp-artifacts/demo1 WORKSPACE=.local-runs/demo1/workspace
export CONFIRM_DEMO_RESET=YES        # the reset guard refuses to wipe anything not named demo/local

# Terminal 1: the app (reads the rest of its config from .env).
uv run python -m scripts.workbench dev

# Terminal 2: the suite.
export MVP_APP_URL=http://localhost:13000 MVP_API_URL=http://localhost:18000
export MVP_RAW_TRACE_ROOT=.local-runs/demo1/logs/sdk-events
export MVP_RESET_BEFORE_RUN=1
export MVP_EVAL_SCOPE=all            # all | atomic | workflow
npm run eval:mvp
```

Success prints the evidence and scorecard paths and a summary like:

```text
"atomic":    { "passed": 10, "failed": [] },
"workflows": { "passed": 1,  "failed": [] },
"checks":    { "passed": 180, "total": 180 }
```

Advisory Foundry scoring of that evidence afterwards:

```bash
export MVP_RESULTS='evidence/mvp/local-synthetic/agent-evals/<run>/results.json'
export FOUNDRY_PROJECT_ENDPOINT='https://<account>.services.ai.azure.com/api/projects/<project>'
export FOUNDRY_JUDGE_DEPLOYMENT='<judge-deployment>'
uv run python -m scripts.workbench eval foundry
```

When a run stops before any case executes, the message names which precondition failed:

| Message | Fix |
|---|---|
| `live evidence requires a clean Git worktree` | Commit (or stash) your changes first. |
| `Set MVP_RESET_BEFORE_RUN=1` | Export it — it is the destructive-reset acknowledgement. |
| `COSMOS_DATABASE and COSMOS_CONTAINER must be explicitly named local/demo targets` | Both names must contain the run id and `demo` or `local`. |
| `ENOENT … \logs` | `MVP_RAW_TRACE_ROOT` must point at the running app's `sdk-events` directory. |
| `403 … Public access is disabled` (mid-case, as a `turn_exception`) | The model account is private-endpoint-only; use a reachable deployment. |

## Authoring a new gold standard

Copy an entry in `tests/evals/mvp-cases.json` and fill in the three parts: the **prompt** (and
actor), the **expected tool call(s)** (`toolCall` with exact `args` or an `argsInclude` subset,
plus `requiredToolNames`/`forbiddenToolNames`), and the **end state**
(`engagementAfter`, `stateChanged`, a blast-radius invariant, or `safeNonExecution` for cases
that must refuse). A scenario can also expect the agent to do nothing but ask: `zeroToolResults`
with `assistantResponseRequired` (see `ACME-8-vague-create` — "Create a new engagement." should
get a clarifying question, not a guessed create).

A new case is not registered until every canonical binding knows it — the deterministic evidence
tests enforce each of these, so a missed one fails loudly rather than silently shrinking coverage:

1. `scripts/mvp_eval_manifest.mjs` — add the id to `atomicCaseIds` (the scorecard's hard gate
   accepts only ids on this list).
2. `tests/evals/judge-rubrics.json` — add the case's three advisory-judge questions
   (accuracy, leakage, tone); the judge record must bind the complete rubric.
3. If the case uses a **new tool**, teach the graders: the tool's result operation goes in
   `validEventSequence`'s operation map and, for write tools, in
   `ENGAGEMENT_WRITE_OR_NAVIGATE_TOOLS` (both in `scripts/mvp_evidence.mjs`). If the product's
   model-visible output changed shape, update the independent grounding renderers there too —
   they deliberately re-implement the product's formatting and must be changed in lockstep.
4. The evidence tests pin suite-wide aggregates (case counts, judgment counts, synthetic latency
   sums, tamper counter-examples); a count assertion failing after you add a case is the
   binding working — update the pinned arithmetic deliberately.

Then run the suite live before shipping the case: expectations that look right on paper
(argument phrasing the model won't reproduce, array assertions against a fixture that isn't
empty) only prove themselves against a real run.
