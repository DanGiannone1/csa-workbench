# Testing Charter

> **Human-owned document**
>
> Agents must not edit, replace, move, delete, or create another file that competes with this one
> unless the user explicitly approves changes to this named file in the current conversation.

Tests show whether user-relevant behavior matches a stated expectation for a defined action, input,
and starting state. A successful command matters only when it exercises the behavior being changed
and checks the expected result.

## Testing standard

- State the behavior, starting conditions, action, expected result, and observed result.
- Exercise running behavior whenever the repository provides a practical way to do so.
- Include failures, boundaries, permissions, stored changes, and component interactions when they
  matter to the risk.
- Use source review to find problems, but do not describe runtime behavior as checked when the
  application was not run.
- Report what ran, what passed, what failed, and what was not checked.

Choose the amount of testing based on the likely impact of an error. Access control, stored data,
public contracts, concurrency, recovery, and deployment changes need stronger independent checks.

## The four layers of testing

Every check in this repository sits in one of four layers. The dividing lines are **where the
model enters** and **where ground truth exits**:

| Layer | What's under test | Graded by | Where |
|---|---|---|---|
| 1 · Unit | A function's logic (e.g. the status-note validator) | Code | pytest suites run by `npm run verify:ci` |
| 2 · Integration | The plumbing — a tool or endpoint does what it's told when called directly (a status update lands; a viewer gets 403) | Code | TestClient suites in [`tests/`](../tests/), `scripts/api_probe.py`, `scripts/mvp_playwright.mjs` |
| 3 · Deterministic agent evals | The **agent's choices** — given a natural-language prompt, did the right actions happen, does app/database state match the gold contract, and did nothing else change | Code | `npm run eval:mvp` over [`tests/evals/`](../tests/evals/) — see [agent-evals.md](agent-evals.md) |
| 4 · LLM-as-judge | The **answer's quality** — clear, complete, grounded, helpful — where no assertable ground truth exists | A judge model | `npm run eval:foundry` (Azure AI Foundry built-in evaluators), plus a checked-in set of judge questions a human answers today ([`tests/evals/judge-rubrics.json`](../tests/evals/judge-rubrics.json)) — see [agent-evals.md](agent-evals.md) |

The model enters at layer 3: layers 1–2 test deterministic systems deterministically, so they gate
every change. Layer 3 is a deterministic grader pointed at a non-deterministic subject — runs are
samples, not proofs, so it gates releases and baselines, and the long-run number is a pass rate.
Layer 4 is non-deterministic grading non-deterministic: the same transcript can earn different
verdicts from different judge models, or from the same one twice. That is why layer 4 only ever
advises and never overturns a layer-3 check.

Each layer catches what the one below cannot: layer 2 proves a tool works when called correctly;
layer 3 proves the agent *chooses* to call it correctly from natural language; layer 4 reports
whether the words around those actions served the user.

The sources behind this design are cited claim by claim in the
[design position](agent-evals.md#design-position).

## Running the layers

Use the [local development guide](../docs/guides/local-development.md) for current environment
setup. Browser checks should drive the real frontend and compare the displayed result with
application state and the structured assistant events. Supporting unit, contract, lint, and build
checks do not replace an affected end-to-end user journey.

```bash
npm run verify:ci        # layers 1–2 (plus lint, build, static checks) — every change
npm run eval:mvp         # layer 3 — live app required; see agent-evals.md for env
npm run eval:foundry     # layer 4 — pushes captured evidence to Foundry for judging
npm run eval:waza:gate   # skill routing, tested in isolation (see below)
```

`eval:waza:gate` sits beside the four layers rather than inside them: it checks whether one set of
skill instructions loads at the right moment, using [Waza](https://github.com/microsoft/waza)
(Microsoft's open-source skill-evaluation CLI) against mocked product actions instead of the real
product. Layer-3-style deterministic grading, but of a skill in a laboratory, not of the assistant
in the application.

## Detailed documents

- [Agent evaluation: how it runs](agent-evals.md) — the layer 3–4 pipeline end to end: gold
  contracts, fixture reset, evidence capture, deterministic checks, Foundry upload, and how to
  author a new scenario.
- [Agent evaluation showcase](../docs/guides/eval-showcase.md) — presenting eval results.

## Current status and known gaps

- Layer 3 runs each scenario **once per run**. Repeated trials (pass@k) are a tracked follow-up,
  as are: a dedicated prompt-injection-immunity scenario, re-theming the skill-routing lane onto
  the same test data as the rest, a Foundry project in the workload resource groups, and feeding
  Foundry verdicts into the scorecard's advisory lane.
- No accepted comparison baseline exists yet; the scorecard-history CLI is ready for one.
- A production-traffic lane — sampling real conversations from telemetry into the same reshape →
  Foundry pipeline — is not built yet. The traces it would read are already exported to
  Application Insights; nothing samples them.
