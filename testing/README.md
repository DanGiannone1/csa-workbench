# Testing

How CSA Workbench is tested, built from what actually exists in this repository. The rules for
choosing, running, and reporting checks live in the human-owned
[Testing Charter](../docs/governance/testing-charter.md); this folder documents the layers, the
suites, and how to run them.

## The four layers of testing

Every check in this repository sits in one of four layers. The dividing lines are **where the
model enters** and **where ground truth exits**:

| Layer | What's under test | Graded by | Where |
|---|---|---|---|
| 1 · Unit | A function's logic (e.g. the status-note validator) | Code | pytest suites run by `npm run verify:ci` |
| 2 · Integration | The plumbing — a tool or endpoint does what it's told when called directly (a status update lands; a viewer gets 403) | Code | TestClient suites in [`tests/`](../tests/), `scripts/api_probe.py`, `scripts/mvp_playwright.mjs` |
| 3 · Deterministic agent evals | The **agent's choices** — given a natural-language prompt, did the right actions happen, does app/database state match the gold contract, and did nothing else change | Code | `npm run eval:mvp` over [`tests/evals/`](../tests/evals/) — see [agent-evals.md](agent-evals.md) |
| 4 · LLM-as-judge | The **answer's quality** — clear, complete, grounded, helpful — where no assertable ground truth exists | A judge model | `npm run eval:foundry` (Azure AI Foundry built-in evaluators) and the local advisory judge rubric — see [agent-evals.md](agent-evals.md) |

The model enters at layer 3: layers 1–2 test deterministic systems deterministically, so they gate
every change. Layer 3 is a deterministic grader pointed at a non-deterministic subject — runs are
samples, not proofs, so it gates releases and baselines, and the long-run number is a pass rate.
Layer 4 is non-deterministic grading non-deterministic — judge verdicts have been measured flipping
between judge models on identical evidence — which is why layer 4 only ever advises and never
overturns a layer-3 check.

Each layer catches what the one below cannot: layer 2 proves a tool works when called correctly;
layer 3 proves the agent *chooses* to call it correctly from natural language; layer 4 reports
whether the words around those actions served the user.

## Running the layers

```bash
npm run verify:ci        # layers 1–2 (plus lint, build, static checks) — every change
npm run eval:mvp         # layer 3 — live app required; see agent-evals.md for env
npm run eval:foundry     # layer 4 — pushes captured evidence to Foundry for judging
npm run eval:waza:gate   # skill-routing laboratory (Copilot SDK, mocked product actions)
```

## Documents

- [Agent evaluation: how it runs](agent-evals.md) — the layer 3–4 pipeline end to end: gold
  contracts, fixture reset, evidence capture, deterministic checks, Foundry upload, and how to
  author a new scenario.
- [Agent evaluation showcase](../docs/guides/eval-showcase.md) — presenting eval results.
- [Testing Charter](../docs/governance/testing-charter.md) — the rules (human-owned).

## Current status and known gaps

- Layer 3 runs each scenario **once per run** — repeated trials / pass@k are a tracked follow-up
  (issue #34), as are: restoring a dedicated injection-immunity case, re-theming the Waza lane to
  the Acme fixture, a Foundry project in the workload resource groups, and binding Foundry verdicts
  into the scorecard's advisory lane.
- No accepted comparison baseline exists yet; the scorecard-history CLI is ready for one.
- A production-traffic lane (sampling real conversations from telemetry into the same reshape →
  Foundry pipeline) is blocked on Application Insights wiring (issue #32).
