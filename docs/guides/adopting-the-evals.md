# Adopting the evals in your own repository

You have an application and an agent harness that drives it. This guide explains how to review the
evaluation approach in this repository and apply it to your own: what to read in what order, and
the principles that transfer. The specific graders, fixtures, and tools here belong to this
application — read them as a worked example, not as code to import.

## The idea in three sentences

Every important agent behavior is written down as a gold case: a realistic user request plus a
contract describing what the agent must do (which tools it calls, what ends up saved, what it must
not touch). A harness sends each request to the real agent, and plain code — not another model —
compares what happened against the contract, so the same evidence always produces the same
verdict. A second, optional layer asks a model to judge tone and interpretation, but its opinion
is advisory and can never overturn the deterministic result.

## What to read, in order

Each stop demonstrates one part of the approach. About an hour total; nothing requires running the
application.

1. **[Input prompt + Expected output](../../tests/evals/README.md)** — the whole idea with no
   machinery: real prompts next to the behavior each one must produce.
2. **[The gold dataset](../../tests/evals/mvp-cases.json)** — what a case looks like as data.
   Open two: `ACME-2-update-status` (a write with an expected end state) and `ACME-4-boundary`
   (a request the agent must refuse). Notice that every field is something code can check.
3. **[Testing Charter](../../testing/testing-charter.md)** — how evals sit inside a testing
   strategy: four layers, exactly one of which gates, and why the model judge never does.
4. **[Agent evaluation: how it runs](../../testing/agent-evals.md)** — the pipeline shape:
   reset to pinned data, drive the real agent, capture evidence, grade with code, then send the
   same evidence to a judging service for the advisory layer.
5. **[Gold dataset authoring](../../testing/gold-dataset-authoring.md)** — the full expectation
   vocabulary a case can use, with a validated example.
6. **[Skill evaluation](../../testing/skill-evals.md)** — how to think about evaluating an
   individual skill versus the whole agent, and why "run the suite with the skill, then without"
   is the only test that proves a skill helps.
7. Optional, for mechanics: `scripts/mvp_evidence.mjs` (deterministic graders),
   `scripts/mvp_eval_manifest.mjs` (the pinned suite), `tests/evals/judge-rubrics.json` (the
   judge's questions).

## Principles for incorporating

These are the parts worth carrying into your repository, independent of any tooling.

1. **Write contracts, not transcripts.** For each request, record what must be true afterwards:
   the operation, the tool calls and their key arguments, the saved end state, and the tools that
   must not have been called. Never pin the agent's exact wording — phrasing varies between runs;
   outcomes must not.
2. **Grade with code first; keep the judge advisory.** Everything code can check (tool calls,
   arguments, end state), code checks. Use a model judge only for what code cannot see — tone,
   whether claims are grounded in tool results — and never let it overturn a deterministic
   verdict. If the two disagree, the deterministic layer wins by rule, not by debate.
3. **Include the requests that should not execute.** At least one vague request (the agent should
   ask, not act) and one out-of-bounds request (the agent should refuse). Datasets with only
   happy paths cannot see the most common real failures.
4. **Pin the starting state.** Every run begins from the same small, versioned fixture data. If
   the starting data can drift, results stop being comparable across runs and branches.
5. **Pin the official suite.** Keep an explicit list of which case IDs constitute the gate, and
   make a test fail if that list and the dataset drift apart. This prevents cases from being
   quietly dropped when they become inconvenient.
6. **Record provenance with every result.** Source revision, model, fixture version, and
   clean/dirty state travel with the evidence, so any number can be traced back to exactly what
   produced it.
7. **Keep every result readable by a non-engineer.** Alongside the machine contract, each case
   carries a plain-English statement of the expected behavior, so whether the contract matches
   what users actually need can be reviewed without reading the harness.
8. **Grow the set from real failures.** Start with roughly ten cases drawn from real usage; ten
   cases graded by code beat a hundred graded by impressions. Add a case whenever a real failure
   escapes the suite — every incident is a gold case you were missing.
