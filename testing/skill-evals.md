# Skill evaluation

CSA Workbench ships assistant skills (instruction files the product agent loads for meeting prep,
tasks, calendar, and weekly review). This document is the complete statement of how skills are
evaluated in this repository: what the real test is, what the Waza laboratory is and is not, and
how to run and extend both. It replaces all earlier Waza documents.

## The real test: with the skill, then without

A skill's value claim comes from one experiment:

> Run the standard product evaluation suite with the skill enabled, run it again with the skill
> disabled, and compare quality, safety, and cost — same prompts, same model, same graders.
> Nothing else counts as evidence that a skill works.

The "standard product evaluation suite" is the [product-runtime evaluation](agent-evals.md): real
Deep Agents runtime, real model, real database, deterministic grading of tool calls and saved
state. The meeting-prep skill is exercised there today (the `ACME-3-meeting-prep` case and the
grounding workflow). The with/without comparison is the intended lift experiment for every shipped
skill; it is not yet implemented as a harness switch, and until it is, no document or result in
this repository should claim that a skill improves the product.

Everything below describes the laboratory lane — a development aid, not a source of product
evidence.

## What Waza is — and is not

[Waza](https://github.com/microsoft/waza) is Microsoft's open-source command-line tool for testing
one skill file in isolation: it hands the skill and a set of fake tools to a generic agent (the
GitHub Copilot SDK), feeds it a realistic prompt, records the transcript, and applies pass/fail
rules to what the agent did.

| Waza is | Waza is not |
|---|---|
| A fast scratchpad while writing a skill: "did my rewording break routing?" answered in one isolated run, no product stack | An evaluation of the product — it does **not** run the CSA Workbench Deep Agents product runtime |
| A routing check: the skill fires on the right prompts (including paraphrases) and stays silent on neighboring ones | Evidence of outcome quality, argument correctness, or saved product state |
| A tool-selection check against mocked tools with canned responses | A measure of whether the skill improves the product (that is the with/without experiment above) |
| Laboratory evidence, recorded with provenance for reference | A gate: no Waza result blocks a release, a baseline, or any repository check that calls a model |

Evaluating an individual skill fully means four questions — activation, adherence, outcome, lift.
The laboratory answers the first two cheaply and deliberately stops there; outcomes belong to the
product suite, and lift belongs to the with/without experiment. Never quote a Waza result as
product evidence, and never use one to override a product-runtime result.

`npm run verify:ci` runs only the free deterministic steps (schema validation and skill
readiness). Model-calling Waza runs are always manual, and their results never gate anything.

## Setup and authentication

The repository command downloads the pinned Waza v0.38.3 binary for Windows, macOS, or Linux,
checks its SHA-256 digest, and stores it under `evidence/mvp/local-synthetic/tools/waza/v0.38.3/`.
Do not install an unpinned binary over that path. The
[eval schema](https://github.com/microsoft/waza/blob/v0.38.3/schemas/eval.schema.json),
[task schema](https://github.com/microsoft/waza/blob/v0.38.3/schemas/task.schema.json), and
[grader reference](https://github.com/microsoft/waza/tree/v0.38.3/docs/graders) are the upstream
authority for the file format.

The suites use Waza's `copilot-sdk` executor. A local run therefore needs an active GitHub Copilot
session. If a run stops with `copilot is not authenticated`, sign in once and re-run:

```text
copilot login
```

Use any installed GitHub Copilot CLI. If none is on your PATH, Waza has already downloaded an
embedded copy; on Windows it is at `%LOCALAPPDATA%\copilot-sdk\` (the run's log prints the exact
path), so run that executable with the same `login` argument. The sign-in opens a browser
device-code flow and persists for future runs on the same machine.

In CI, Waza's documented route is a scoped `GITHUB_TOKEN`. A custom Copilot SDK provider
may instead use `COPILOT_BASE_URL`, `COPILOT_PROVIDER`, and the provider credential described in
the [pinned upstream setup](https://github.com/microsoft/waza/blob/v0.38.3/README.md#custom-copilot-sdk-providers).
Never commit a token or paste it into an evidence file.

Before any model call, run both deterministic checks:

```text
npm run eval:waza:validate
npm run eval:waza:check
```

`validate` retrieves the two v0.38.3 schemas from their pinned URLs, rejects a hash mismatch, parses
the checked-in YAML, and validates every eval and task. `check` asks the pinned Waza binary whether
each skill file is ready. Skill readiness does not replace eval-schema validation.

## Mocks and task anatomy

Each `tests/evals/waza/<skill>/eval.yaml` names the skill, executor, model, metrics, task files, and
fake product tools. A mock defines the tool's input shape and a known response. It never contacts
CSA Workbench or changes product data:

```yaml
mcp_mocks:
  - name: csa
    tools:
      create_task:
        input_schema:
          type: object
          required: [title]
        responses:
          - match_schema: { type: object, required: [title] }
            return: { status: committed, resource: { kind: task, id: t-new } }
```

A task supplies the client-like prompt and graders:

```yaml
id: WAZA-TSK-1-direct-create
name: Direct private task request
description: The task skill and create_task tool should be selected; arguments and outcome are not graded.
tags: [advisory, routing, positive]
inputs:
  prompt: Add a High priority task to review the proposal.
expected:
  behavior: { max_tool_calls: 4 }
graders:
  - type: skill_invocation
    config: { mode: exact_match, required_skills: [tasks], allow_extra: false }
  - type: tool_constraint
    config:
      expect_tools: [{ tool: ".*create_task$" }]
      reject_tools: [{ tool: ".*create_event$" }]
```

`skill_invocation` and `tool_constraint` are deterministic over the recorded transcript. They prove
only the routing or tool-name condition they state. A `prompt` grader uses a model to review prose;
it is advisory and can disagree with another judge. The suites do not check tool arguments,
returned status, or saved product outcome.

## Starter suites and building your own

The four checked-in suites double as documentation examples; keep them small and readable.

| Suite | What its tasks show |
|---|---|
| `engagement-meeting-prep` | The full pattern: direct trigger, paraphrased trigger, two does-not-trigger cases, a failure-mode case, and a grounding case |
| `tasks` | The minimal pair: one direct create, one "calendar wording must not trigger the tasks skill" |
| `calendar` | The same minimal pair from the calendar side |
| `weekly-review` | A multi-step workflow trigger, plus "a single task request must not trigger a whole review" |

Every suite carries at least one negative (does-not-trigger) case. That is deliberate: the most
common skill failure in practice is a skill firing when it should stay silent, and a suite with
only positive cases cannot see it.

To test your own skill in about ten minutes:

1. Duplicate the smallest suite: copy `tests/evals/waza/tasks/` as `tests/evals/waza/<your-skill>/`.
2. In `eval.yaml`, point `skill` at your skill file, rename the eval, and replace the `mcp_mocks`
   with the tools your skill expects — each mock needs an input shape and a canned response.
3. In `tasks/`, write at least one positive prompt and one negative prompt.
4. Register the suite in the `WAZA_SUITES` list in `scripts/workbench.py` so the runner picks it up.
5. Run `npm run eval:waza:validate` and `npm run eval:waza:check` (free, no sign-in), then
   `npm run eval:waza:advisory`.

Read a failing task's transcript before changing anything: the transcript shows what the agent
actually did, which is usually more informative than the pass/fail bit.

## Commands by operating system

Run from the repository root. These commands call a model after the two validation commands.
`advisory` runs the advisory-tagged tasks in every suite; `eval:waza` (the `run` action) runs
every task in every suite.

Linux Bash:

```bash
npm run eval:waza:advisory
```

macOS Terminal using Bash or another Bash-compatible shell:

```bash
npm run eval:waza:advisory
```

Windows PowerShell uses the checksum-pinned native Windows binary:

```powershell
npm run eval:waza:advisory
```

The portable Python command installs and verifies the matching Waza v0.38.3 binary on Windows,
macOS, or Linux and records the same provenance on every host. Windows developers who explicitly
prefer WSL can add `--wsl`, for example
`uv run python -m scripts.workbench eval waza advisory --wsl`.

Exit status:

| Exit | Meaning | Evidence behavior |
|---|---|---|
| `0` | Every selected task passed. | Provenance is appended to each result. |
| `1` | One or more tasks failed their graders. | The command continues through every suite, appends provenance to each produced result, then returns `1`. |
| `2` or another higher value | Setup, invalid configuration, or runtime failure. | The command stops because no trustworthy task result may exist; the original status is preserved. |

A failure is a finding to investigate, not a release signal. Waza results never gate a release,
a baseline, or the product suite.

## Evidence and a worked interpretation

Each run writes:

```text
evidence/mvp/local-synthetic/waza/<UTC-time>-<process>-<skill>/
  waza.json
  transcripts/
```

`waza.json` contains Waza's result plus `csaMvpProvenance`: Waza version, source revision before and
after, clean/dirty state, tag, skill name/path/hash, eval path, and time. Waza's canonical config
records the executor, model, and trial count; task entries contain validation details. The Git revision binds tracked
mock definitions; dirty evidence is demonstration-only.

Example interpretation:

| Recorded fact | Plain-English result |
|---|---|
| `status: passed`; required skill and tool validations passed | This sampled prompt selected the intended skill and mocked tool. It does not prove arguments, a saved outcome, or Deep Agents behavior. |
| `status: failed`; `tool_constraint` failed | The sampled prompt selected a forbidden tool or missed a required tool. Read that task's transcript and grader feedback. |
| No `waza.json`; process returned `2` | The suite did not execute reliably. Fix setup or schema errors before interpreting behavior. |

## Repeated trials

One trial is one sample. To request five attempts per task while retaining repository provenance:

Linux or macOS:

```bash
CSA_WAZA_TRIALS=5 npm run eval:waza:advisory
```

Windows PowerShell:

```powershell
$env:CSA_WAZA_TRIALS='5'
npm run eval:waza:advisory
```

WSL is an optional fallback and uses the Linux command inside its shell.

Record the trial count and every outcome. `pass@k` is the chance that at least one of *k*
independent attempts succeeds; `pass^k` is the chance that all *k* attempts succeed. The fraction
of individual attempts that passed is the **pass rate**, not pass@k. Compare only compatible
source, skill, mocks, model, runner, and trial conditions.

**Next:** Use [product-runtime evaluation](agent-evals.md) for real application behavior — the only
lane that supports a claim about CSA Workbench.
