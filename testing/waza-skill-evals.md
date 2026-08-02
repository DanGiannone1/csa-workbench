# Waza skill-evaluation guide

This guide covers **Waza**, Microsoft's open-source command-line tool for testing one set of skill instructions in a controlled laboratory. It does **not** run the CSA Workbench Deep Agents product runtime. A Waza result can show that a skill is likely to load and use mocked tools appropriately; it cannot prove that the deployed application used the same skill correctly.

Start with [the eval introduction](../tests/evals/README.md) if these terms are new.

## What Waza checks

A Waza evaluation contains:

- one skill's `SKILL.md` instructions;
- a small set of fake product tools (**mocks**) with known responses;
- natural-language tasks;
- checks that inspect which skill loaded and which mocked tools were used; and
- optional language-quality checks that are explicitly advisory.

The source files live under `tests/evals/waza/<skill-name>/`. The four product skills have a matching evaluation directory: `engagement-meeting-prep`, `tasks`, `calendar`, and `weekly-review`.

## Read a task before you edit it

```yaml
id: WAZA-TASK-1-direct-trigger
inputs:
  prompt: Add a High priority task to review the proposal.
graders:
  - type: skill_invocation
    config:
      required_skills: [tasks]
```

The prompt is the client-visible input. The grader is the technical check that decides whether the right instructions loaded. Tool constraints then verify the safe action boundary. A prompt grader uses a model to review prose; label it advisory because it can disagree with another model.

## Run it

Run the readiness check first. It validates that Waza can load the skill instructions:

```text
npm run eval:waza:check
```

The existing gate covers meeting preparation because it has recorded stability evidence. The other three skills are advisory while they collect repeated, reviewed results. The advisory command runs those suites and records the exact skill hash, Waza version, source revision, model, and tag.

```text
npm run eval:waza:advisory
```

On Linux and macOS, run the command from a Bash-compatible terminal. The pinned Waza runner does
not currently support native Windows. On Windows, run it in WSL; it changes no product data because
every product action is mocked. The repository's cross-platform wrapper work may make command
selection easier, but it cannot turn an unsupported Waza binary into native Windows support.

## Gate versus advisory

| Type | Meaning | Promotion rule |
|---|---|---|
| Gate | A deterministic, stable check that blocks a candidate evaluation result when it fails. | Keep task inputs, mocks, tool constraints, runner, and evidence provenance fixed; collect repeated clean runs and obtain reviewer approval. |
| Advisory | Useful signal that does not block release acceptance. | Use this while a task, rubric, model, or stability evidence is still being refined. |

Never call an advisory language grader proof. Never use a Waza result as Deep Agents runtime evidence. Pair it with `npm run eval:mvp` for the live application and browser checks for the user journey.

## Trials, evidence, and limits

One run is one sample. If a task uses multiple trials, record the trial count. `pass@k` is the chance that at least one of *k* independent attempts succeeds; `pass^k` is the chance that every attempt succeeds. Store only evidence that names the skill version, source revision, mocks, model, runner, and time. Compare results only when those conditions are compatible.

**Next:** For a real product behavior claim, use [product-runtime evaluation](agent-evals.md). For a client-readable explanation, return to [the eval introduction](../tests/evals/README.md).
