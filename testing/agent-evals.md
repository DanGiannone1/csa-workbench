# Agent evaluation: how it runs

This guide explains the agent-eval pipeline end to end: where the scenarios live, how a run
executes against the real product, what the deterministic grader checks, and how the same
evidence is scored by Azure AI Foundry's evaluators as an advisory second opinion.

The one-line mental model: **write down what good looks like before the run; drive the real
product; grade the facts with code (gate); grade the language with LLM evaluators (advise).**

This guide covers layers 3 and 4 of the [four-layer testing model](testing-charter.md); current status and
known gaps are tracked there too.

## The pieces

| Piece | Where | What it is |
|---|---|---|
| Gold contracts (atomic) | `tests/evals/mvp-cases.json` | 6 single-prompt scenarios: prompt, actor, expected tool calls + exact args, forbidden tools, expected DB end state |
| Gold contract (workflow) | `tests/evals/mvp-workflows.json` | 1 multi-turn conversation (4 turns) with per-turn contracts plus conversation-level invariants |
| Canonical manifest | `scripts/mvp_eval_manifest.mjs` | Freezes which case/workflow ids count as the official suite and which are all-or-nothing safety cases |
| Fixture | `session-container/appdb.py` (`_seed_engagements`), reset via `scripts/reset_demo_state.py` | Known demo data (`acme-ai-v1`): actors dan/ava/sam and three engagements around the "Acme Internal AI Chatbot" narrative |
| Driver | `scripts/mvp_agent_eval.mjs` | Runs the suite against the live app and writes evidence |
| Grader | `scripts/mvp_evidence.mjs` | `evaluateCase` / `evaluateWorkflow`: the deterministic checks |
| Scorecard | `scripts/mvp_scorecard.mjs` (+ `mvp_scorecard_history.mjs`) | Aggregates evidence into the product hard gate, Waza lane, and advisory-judge lane |
| Foundry upload | `scripts/foundry_evidence_rows.py`, `scripts/foundry_eval_upload.py` | Converts evidence to Foundry's agent-message schema and scores it server-side with the built-in agent evaluators |
| Skill laboratory | `scripts/waza_eval.sh`, `tests/evals/waza/**` | Separate lane: one skill tested in isolation with mocked product actions (not covered further here) |

## What happens on `npm run eval:mvp`, step by step

1. **Preconditions.** The driver refuses to run without `MVP_RESET_BEFORE_RUN=1` and
   `DEMO_PASSWORD`, refuses non-loopback API targets, and refuses a dirty git worktree —
   evidence is only produced from a known revision.
2. **Fixture reset — before every scenario, not once per run.** `reset_demo_state.py` is
   guarded so it can only ever point at a loopback Cosmos emulator with demo/local-named
   database and container. It deletes everything, reseeds through the same code path the
   product uses, and returns the fixture version + a SHA-256 identity that the driver verifies
   never drifts mid-run.
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
   declares (`applicablePrimaryCheckNames`). Most scenarios score per-check (`partial`);
   safety cases (the manifest's `safetyAtomicCaseIds`) are all-or-nothing. Workflows re-grade
   each turn the same way plus conversation-level invariants.
7. **Evidence out.** Everything — prompts, events, raw traces, before/after state, verdicts —
   is written to `evidence/mvp/local-synthetic/agent-evals/<run>/results.json`, with a
   scorecard beside it. The process exits non-zero if anything failed.

## What the deterministic checks verify

Six families (the full set is ~28 named checks in `mvp_evidence.mjs`):

- **Protocol** — the event stream is well-formed: one terminal event, complete tool-call
  lifecycles, result operations matching their tools, navigation bound to a real result.
- **Tool calls** — the expected call happened with exactly the expected arguments; required
  tools present; forbidden tools absent; no argument or result targeted any engagement other
  than the declared one (blast radius of *intent*, not just outcome).
- **Database end state** — read back through the product API afterward: the named engagement
  has the expected status/note; nothing else changed (single-domain invariants
  `onlyNamedEngagementMayChange` / `onlyPersonalAggregateMayChange`, or the joint
  `onlyEngagementAndPersonalAggregateMayChange` when one prompt legitimately writes an
  engagement *and* a personal record); safety cases prove no write was committed.
- **Grounding** — for read scenarios, the tool output the model saw is re-rendered from the
  pre-turn database and must match byte-for-byte: the brief cannot contain invented facts.
- **Corroboration** — every client-visible tool result must match the server-side trace record.
- **Conversation integrity** (workflows) — one session throughout, each turn starting from the
  previous turn's exact end state, expected turn count, expected final engagement state.

Assistant wording is deliberately **recorded but never scored** here — free-form prose cannot
be pass/failed deterministically. The checks confirm an answer exists and that what the model
was told is true; judging the answer's quality is the advisory lane's job.

## The Foundry advisory lane

```mermaid
flowchart LR
    A["Product assistant<br/>DeepAgents SDK · LangGraph"] --> B["Eval harness<br/>captures each run as evidence"]
    B --> C["Deterministic checks<br/>gate"]
    B --> D["Foundry Evaluations<br/>Azure AI Projects SDK · advise"]
```

Layer 4 is three mechanical steps:

1. **Save the transcript.** The layer-3 run already recorded everything: the prompt, every tool
   call with arguments and results, and the answer text (in `results.json`).
2. **Convert to Foundry's expected shape** (`scripts/foundry_evidence_rows.py`). Each scenario or
   workflow turn becomes one row:

   ```json
   {
     "item_id": "ACME-2-update-status",
     "harness_pass": true,
     "user_request": "…set that engagement to Yellow with the exact reason…",
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
   returned), and refuses evidence whose ids aren't in the canonical suite.
3. **Send** (`scripts/foundry_eval_upload.py`): two API calls — `evals.create` names the built-in
   evaluators and the judge deployment; `evals.runs.create` hands over the rows. Judging runs
   server-side in Foundry; the run appears in the portal with per-row scores and reasoning.

`npm run eval:foundry` performs steps 2–3 against a finished evidence file, with tool
definitions generated from `session-container/mvp_tool_schemas.py` and ground-truth tool
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

Foundry results are **advisory by design**: LLM judges are valuable for language quality and
task-level second opinions, but they are policy-blind and judge-model-sensitive. Where a judge
disagrees with a deterministic check, the deterministic check is authoritative.

## Design position (validated against the field, July 2026)

- **Grading final database state in code is the mainstream benchmark pattern, not a novelty.**
  τ-bench and τ²-bench (Sierra) grade by hashing the entire post-run database against a gold
  state derived by replaying reference actions on a fresh database — no LLM judge in the reward
  path; AgentBench's DB track and WebArena/OSWorld likewise verify final environment state with
  code. τ²-bench's docs state the agent "is not required to take this specific path; any sequence
  of tool calls that produces an equivalent DB end state passes."
- **Trajectory (tool-sequence) grading is the documented anti-pattern.** Anthropic's eval
  guidance: checking "a sequence of tool calls in the right order" is "too rigid and results in
  overly brittle tests." Contracts here assert outcomes and safety envelopes, not paths.
- **Isolated deployment + synthetic test identities is Microsoft's documented procedure** for
  automated testing (separate test tenant, dedicated test users, credentials in Key Vault, MFA
  exclusions — production-tenant auth cannot be automated by design). The demo identity mode is
  this pattern implemented in-app; no eval framework ships scripted multi-identity testing at all.
- **Foundry's built-in agent evaluators are transcript-graded LLM judges with no concept of
  environment state**; Microsoft's own mechanism for outcome checking is custom evaluators. The
  deterministic layer here is therefore strictly stronger than the vendor default and matches the
  benchmark literature.
- **The field's documented risk is gold-state authoring errors** (Amazon's τ²-bench-verified found
  reference solutions violating the domain's own policies). Gold contracts get independent review
  like any other code.

### Sources

State-graded benchmarks (final DB/environment state compared in code):

- τ-bench — [paper](https://arxiv.org/abs/2406.12045) ·
  [repo](https://github.com/sierra-research/tau-bench) (whole-DB hash vs gold state; pass^k)
- τ²-bench — [evaluation docs](https://github.com/sierra-research/tau2-bench/blob/main/docs/evaluation.md)
  ("any sequence of tool calls that produces an equivalent DB end state passes")
- AgentBench — [paper](https://arxiv.org/abs/2308.03688) (DB track: table hash vs gold hash)
- WebArena — [paper](https://arxiv.org/abs/2307.13854) (code assertions on live final state)
- τ²-bench-verified — [repo](https://github.com/amazon-agi/tau2-bench-verified) (gold-state
  authoring errors as the primary failure mode)

Against trajectory grading; for isolated, reset environments:

- Anthropic, [Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
  (tool-sequence checks "too rigid… overly brittle"; clean environment per trial)

Test identities and environments as documented enterprise practice:

- Microsoft identity platform — [Set up a test environment](https://learn.microsoft.com/en-us/entra/identity-platform/test-setup-environment) ·
  [Run automated integration tests](https://learn.microsoft.com/en-us/entra/identity-platform/test-automate-integration-testing)
  (separate test tenant, dedicated test users, MFA exclusions; production auth is not automatable)
- Playwright — [authentication guidance](https://playwright.dev/docs/auth) (pre-created test
  accounts, one per parallel worker)

Vendor evaluator scope (why the deterministic layer is ours to build):

- Azure AI Foundry — [agent evaluators](https://learn.microsoft.com/en-us/azure/foundry/concepts/evaluation-evaluators/agent-evaluators)
  (transcript-graded LLM judges; no environment-state concept — custom evaluators are the
  outcome-checking mechanism)

## The one-command demo

To watch a single prompt travel through both layers — deterministic verdict printed fact by
fact, then the same transcript judged in Foundry:

```bash
npm run eval:demo ACME-2-update-status     # any canonical case id; app must be running
```

It prints the agent's tool calls with arguments, the database before/after from authoritative
reads, every credited check ✓/✗, then ships the transcript to Foundry and prints the portal
link (set `FOUNDRY_PROJECT_ENDPOINT` and `FOUNDRY_JUDGE_DEPLOYMENT`). Demo runs land in
`.local-runs/eval-demo/` and are not evidence — the provenance gates of `eval:mvp` are skipped.

## Running it

```bash
# 1. App up (terminal 1) — see docs/guides/local-development.md for the full env
uv run dev.py

# 2. Full suite (terminal 2; same env values as the app)
export MVP_API_URL='http://127.0.0.1:18000'
export MVP_RAW_TRACE_ROOT='<run logs>/sdk-events'
export MVP_RESET_BEFORE_RUN=1
export MVP_EVAL_SCOPE=all          # all | atomic | workflow
npm run eval:mvp

# 3. Advisory Foundry scoring of that evidence
export MVP_RESULTS='evidence/mvp/local-synthetic/agent-evals/<run>/results.json'
export FOUNDRY_PROJECT_ENDPOINT='https://<account>.services.ai.azure.com/api/projects/<project>'
export FOUNDRY_JUDGE_DEPLOYMENT='<judge-deployment>'
npm run eval:foundry
```

## Authoring a new gold standard

Copy an entry in `tests/evals/mvp-cases.json` and fill in the three parts: the **prompt** (and
actor), the **expected tool call(s)** (`toolCall` with exact args, plus
`requiredToolNames`/`forbiddenToolNames`), and the **end state**
(`engagementAfter`, `stateChanged`, a blast-radius invariant, or `safeNonExecution` for cases
that must refuse). Then add the id to `scripts/mvp_eval_manifest.mjs` — the scorecard accepts
only the canonical suite, so the manifest and the deterministic evidence tests
(`npm run test:mvp-evidence`) keep the two in lockstep.
