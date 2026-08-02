# Waza skill-evaluation guide

Waza is Microsoft's command-line laboratory for testing one set of skill instructions with fake
product tools. It does **not** run the CSA Workbench Deep Agents product runtime. A Waza result can
show routing and mocked-tool behavior; only `npm run eval:mvp` and the browser journey can support a
claim about the real application.

Start with [Input prompt + Expected output](../tests/evals/README.md) if evaluations are new to you.
This repository pins [Waza v0.38.3](https://github.com/microsoft/waza/tree/v0.38.3). Its
[eval schema](https://github.com/microsoft/waza/blob/v0.38.3/schemas/eval.schema.json),
[task schema](https://github.com/microsoft/waza/blob/v0.38.3/schemas/task.schema.json), and
[grader reference](https://github.com/microsoft/waza/tree/v0.38.3/docs/graders) are the upstream
authority for the file format.

## Setup and authentication

The repository command downloads the pinned Windows, macOS, or Linux binary, checks its SHA-256 digest, and
stores it under `evidence/mvp/local-synthetic/tools/waza/v0.38.3/`. Do not install an unpinned binary
over that path.

The suites use Waza's `copilot-sdk` executor. A local run therefore needs an active GitHub Copilot
session. In CI, Waza's documented route is a scoped `GITHUB_TOKEN`. A custom Copilot SDK provider
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
each of the four `SKILL.md` files is ready. Skill readiness does not replace eval-schema validation.

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
it is advisory and can disagree with another judge. The current task, calendar, and weekly-review
suites do not check tool arguments, returned status, or saved product outcome.

## Commands by operating system

Run from the repository root. These commands call a model after the two validation commands.

Linux Bash:

```bash
npm run eval:waza:gate
npm run eval:waza:advisory
```

macOS Terminal using Bash or another Bash-compatible shell:

```bash
npm run eval:waza:gate
npm run eval:waza:advisory
```

Windows PowerShell uses the checksum-pinned native Windows binary:

```powershell
npm run eval:waza:gate
npm run eval:waza:advisory
```

The portable Python command installs and verifies the matching Waza v0.38.3 binary on Windows,
macOS, or Linux and records the same provenance on every host. Windows developers who explicitly
prefer WSL can add `--wsl`, for example
`uv run python -m scripts.workbench eval waza advisory --wsl`.

## Gate, advisory, and exit status

The meeting-prep routing suite is the existing gate. Tasks, calendar, and weekly-review are
advisory routing/tool-selection probes until repeated clean results are reviewed.

| Exit | Meaning | Evidence behavior |
|---|---|---|
| `0` | Every selected task passed. | Provenance is appended to each result. |
| `1` | One or more tasks failed their graders. | The advisory command continues through all three suites, appends provenance to each produced result, then returns `1`. |
| `2` or another higher value | Setup, invalid configuration, or runtime failure. | The command stops because no trustworthy task result may exist; the original status is preserved. |

An advisory failure is a finding to investigate, not a release gate. Never use Waza to override a
Deep Agents product-runtime failure.

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

## Repeated trials and promotion

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
of individual attempts that passed is the **pass rate**, not pass@k. Repeated trials do not promote
an advisory suite automatically: compare only compatible source, skill, mocks, model, runner, and
trial conditions, then obtain independent reviewer approval.

**Next:** Use [product-runtime evaluation](agent-evals.md) for real application behavior, or return
to the [beginner eval guide](../tests/evals/README.md) for client-facing examples.
