# Working with coding agents

CSA Workbench supports Codex, Claude Code, and GitHub Copilot independently. A developer can use any
one of them after cloning the repository; no agent needs another agent's native folder.

## Entry points

| Coding agent | Entry point | Native files |
|---|---|---|
| Codex | `AGENTS.md` | `.codex/agents/` and `.codex/skills/` |
| Claude Code | `CLAUDE.md`, which imports `AGENTS.md` | `.claude/agents/` and `.claude/skills/` |
| GitHub Copilot | `.github/copilot-instructions.md` and `AGENTS.md` | `.github/agents/` and `.github/skills/` |

Start each tool normally from the repository root. Claude users may start the optional lead profile
with `claude --agent project-lead`.

## Repository skills

Each coding agent has the same four skills:

- `agentic-sdlc`
- `engineering-operating-standards`
- `testing`
- `agentic-design`

The native `SKILL.md` files are small pointers. The complete instructions live once in
[`docs/repo-agent-skills/`](../repo-agent-skills/README.md). Local browser testing and safe Azure
verification are both part of the `testing` skill.

These development skills are not product features. The skills used by the CSA Workbench assistant
live separately in `backend/assistant/product-skills/`.

## Optional agent roles

| Responsibility | Claude Code | Codex | GitHub Copilot |
|---|---|---|---|
| Lead | `project-lead` | `project-lead` | `project-lead` |
| Difficult analysis and independent review | `opus` | `sol` | Built-in worker |
| Implementation | `sonnet` | `terra` | Built-in worker |
| Fast read-only investigation | `haiku` | `luna` | Built-in worker |

The lead communicates with the user and owns decisions. Workers receive bounded assignments and
return evidence. Claude workers do not delegate to other Claude workers.

## Check the scaffold

After changing agent files, run the static check:

```text
uv run --with pytest pytest -q tests/test_agent_guidance.py
```

Then check the runtime you changed from a fresh session:

- Claude Code: open `/agents` and confirm `project-lead`, `opus`, `sonnet`, and `haiku`; confirm the
  four skills are available.
- Codex: run `codex debug prompt-input "List repository instructions and skills. Do not change files."`
  and confirm the four skills appear once; confirm the custom agents are available for delegation.
- GitHub Copilot CLI: run `/instructions` and `/skills list`; confirm its entry point and four skills.

If an installed client does not expose an inventory command, record the client version and that
limitation instead of treating a model response as proof of discovery.

## Create a customer archive

The native Claude and Codex folders stay in the development repository. To create a customer copy
without those folders, archive a committed revision from the repository root:

```text
git archive --format=zip --output csa-workbench-customer.zip HEAD
```

`.gitattributes` excludes `.claude/`, `.codex/`, `CLAUDE.md`, and itself from that archive.
`AGENTS.md` and `.github/` remain so the exported repository retains general and Copilot guidance.
`git archive` includes committed files only, so commit the intended customer revision first.

## Local and Azure work

Use the [local development guide](local-development.md) for setup and local runs. Use the
[deployment guide](deployment.md) for Azure planning, deployment, and verification. Inspecting an
Azure target or running verification does not authorize deployment; apply only after the user has
approved the exact target and plan. Once that approval is clear, the agent may use the exact
confirmation printed by that plan. A plan-only request never permits deployment.
