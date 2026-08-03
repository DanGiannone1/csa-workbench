# Adopting the evals in your own repository

This guide is for a team reviewing how CSA Workbench evaluates its AI assistant and wanting to
apply the same approach to their own agent. It tells you what to read in what order, and then how
to build your own gold-standard dataset. Reviewing takes about an hour; nothing here requires
running the application.

## The idea in three sentences

Every important assistant behavior is written down as a gold case: a realistic user request plus a
contract describing what the assistant must do (which tools it calls, what gets saved, what it must
not touch). A test harness sends each request to the real assistant and plain code — not another
AI — compares what happened against the contract, so the same evidence always produces the same
verdict. A second, optional layer asks a model to judge tone and interpretation, but its opinion is
advisory and can never overturn the deterministic result.

## What to read, in order

1. **[Input prompt + Expected output](../../tests/evals/README.md)** — the beginner's view.
   Real prompts from the test set next to what a client would expect to see. Read this first; it
   shows the whole idea without any machinery.
2. **[The gold dataset itself](../../tests/evals/mvp-cases.json)** — the actual cases. Pick two:
   `ACME-2-update-status` (a simple write with an expected end state) and `ACME-4-boundary` (a
   request the assistant must refuse). Every field you see is compared by code.
3. **[Testing Charter](../../testing/testing-charter.md)** — the rules. Four layers of testing,
   which layer gates a release, and why the AI judge never does.
4. **[Agent evaluation: how it runs](../../testing/agent-evals.md)** — the pipeline. How the
   harness resets data, sends prompts, captures evidence, grades it, and uploads to Azure AI
   Foundry for the advisory judge layer.
5. **[Gold dataset authoring](../../testing/gold-dataset-authoring.md)** — the reference for every
   expectation field a case can use, with a validated worked example.
6. **[Skill evaluation](../../testing/skill-evals.md)** — how individual skills are evaluated,
   what the isolated Waza laboratory is for, and the with/without-skill experiment that measures
   whether a skill actually helps.
7. Optional, for the mechanics: `scripts/mvp_evidence.mjs` (the deterministic graders),
   `scripts/mvp_eval_manifest.mjs` (the pinned list of cases that counts as the official suite),
   and `tests/evals/judge-rubrics.json` (the questions the advisory judge is asked).

To watch it run instead of reading, follow the [eval showcase](eval-showcase.md), which walks
through the results in a browser, or the "Running it" section of
[agent-evals.md](../../testing/agent-evals.md) to execute the suite yourself.

## Building your own gold-standard dataset

The dataset is the valuable part; the harness is replaceable. The method:

1. **Collect ten real requests.** Take them from actual usage of your agent — the common cases,
   not the clever ones. Write each as the user would type it, including one vague request and one
   request the agent should refuse or ask about instead of executing. Datasets with only
   happy-path cases cannot see the most common failures.
2. **Write the contract, not the prose.** For each request, record what must be true afterwards:
   which operation ran, which tool was called with which key arguments, what the saved record must
   contain, and which tools must not have been called. Do not write down the exact sentence the
   assistant should say — wording varies run to run; outcomes must not.
3. **Give every case a stable ID and a client-readable expected output.** The ID anchors grading
   and history; the plain-English expected output lets a non-engineer review whether the contract
   matches what users actually want.
4. **Pin the starting state.** Every run begins from the same small, versioned fixture data.
   If the starting data can drift, results stop being comparable.
5. **Grade with code first.** Compare tool calls, arguments, and end state programmatically.
   Add an AI judge only afterwards, only for qualities code cannot check (tone, grounding of
   claims in tool results), and keep its verdicts advisory. If a judge disagrees with the
   deterministic layer, the deterministic layer wins.
6. **Pin the official suite.** Keep an explicit list of which case IDs constitute the release
   gate, and make a test fail if the list and the dataset drift apart. This prevents cases being
   quietly dropped when they become inconvenient.

Start small: ten cases graded by code beat a hundred graded by vibes. Grow the set when a real
failure escapes it — every production incident is a gold case you were missing.

## What to take and what to leave

Take the pattern: gold contracts, deterministic grading, a pinned suite, evidence with provenance,
and an advisory-only judge. The specific harness, graders, and fixtures in this repository are
built around CSA Workbench's tools and data model — read them as a worked example rather than
importing them wholesale. The one external dependency worth noting: the advisory judge layer uses
Azure AI Foundry's evaluation service, which any Azure AI project can call with its own models.
