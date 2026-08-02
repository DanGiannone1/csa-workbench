# Working with coding agents

This guide is for a human collaborator using a CLI coding agent in the repository.

## Local work

1. Start with [AGENTS.md](../../AGENTS.md). Claude also reads [CLAUDE.md](../../CLAUDE.md), and
   GitHub Copilot also reads [`.github/copilot-instructions.md`](../../.github/copilot-instructions.md).
2. Confirm the requested goal, boundaries, success criteria, and approval before editing.
3. Inspect the current source and worktree. Preserve other people's changes.
4. Use the isolated run instructions in [local development](local-development.md).
5. Supply or select secrets, Azure account choices, model values, and Cosmos settings yourself.
6. Run the relevant repository and browser checks and inspect the resulting behavior.

Do not paste, print, or commit secrets.

## Supported developer-agent entry points

The repository supports a small, documented entry point for each runtime. The canonical
independence and skill-boundary policy is [Agentic Design](../governance/agentic-design.md).

| Runtime | Repository entry points | Native additions | What this repository does not promise |
|---|---|---|---|
| Claude Code | `AGENTS.md`, then `CLAUDE.md` | `.claude/agents`, `.claude/skills`, and communication guidance | That every developer has the optional PPEL or the same local permissions and models. |
| Codex | `AGENTS.md` | `.codex/skills` | That a locally configured profile, including PPEL, exists after a fresh clone. |
| GitHub Copilot CLI | `.github/copilot-instructions.md`, `AGENTS.md`, and `CLAUDE.md` | `.github/skills`; it may also discover `.claude/skills` | That the CLI is installed, or that a product-assistant skill is a developer skill. |
| VS Code agent mode | `.github/copilot-instructions.md` and `AGENTS.md` | `.github/skills` | That VS Code agent mode discovers `CLAUDE.md`, or that an IDE can enforce an instruction. |
| Copilot cloud coding agent | `.github/copilot-instructions.md`, `AGENTS.md`, and `CLAUDE.md` | `.github/skills`; it may also discover `.claude/skills` | That every GitHub plan or organization enables the coding agent, or that a product-assistant skill is a developer skill. |

GitHub documents `.github/copilot-instructions.md` as the repository-wide Copilot instruction
location and `AGENTS.md` as agent guidance. Copilot CLI and the cloud coding agent can also use
`CLAUDE.md`; VS Code agent mode should be checked against `AGENTS.md`, not `CLAUDE.md`. GitHub
documents `.github/skills/<name>/SKILL.md` and `.claude/skills/<name>/SKILL.md` as project skill
locations for the CLI and cloud agent. We deliberately keep repository workflow skills there and
never copy the shipped product skills from `backend/assistant/product-skills/` into either folder.
See GitHub's [custom-instruction support reference](https://docs.github.com/en/copilot/reference/custom-instructions-support)
when adding a new Copilot surface.

## Discovery smoke tests

Run these after changing an entry point or developer skill. They confirm discovery and references;
they do not claim that an instruction can technically enforce a runtime permission.

1. **Static check, every platform:** run `uv run --with pytest pytest tests/test_agent_guidance.py`
   from the repository root. It checks the entry-point links, product-skill allowlist, image
   packaging, and that product skills are not duplicated into developer skill folders.
2. **Claude Code:** run `/memory` or `/context` when available and verify `AGENTS.md` and the
   `@AGENTS.md` import from `CLAUDE.md` are listed. PPEL communication guidance is native/manual;
   no repository hook enforces it.
3. **Codex:** from the repository root, run this model-free inventory command:

   ```bash
   codex debug prompt-input "Inventory repository guidance and discovered skills. Do not change files."
   ```

   The JSON evidence must include the model-visible repository instruction context and the
   discovered `.codex/skills` entries. It does not need a model, a profile, or a file change.
4. **GitHub Copilot CLI:** start a fresh session and run `/instructions`, then `/skills list`.
   Expect the CLI to report `.github/copilot-instructions.md`, `AGENTS.md`, and `CLAUDE.md`, plus
   skills from `.github/skills` and any applicable `.claude/skills`. If `copilot` is not installed,
   or the installed CLI has no inventory command, record that limitation rather than inferring
   discovery from a model answer.
5. **VS Code agent mode:** start a fresh agent-mode chat in the repository workspace. Check the
   references that VS Code exposes for `.github/copilot-instructions.md` and `AGENTS.md`. Do not
   use `CLAUDE.md` as evidence for this surface. If the client does not expose an instruction
   inventory, record the client version and the limitation rather than treating a chat reply as
   proof.
6. **Copilot cloud coding agent:** inspect the coding-agent task's instruction references when the
   GitHub UI exposes them. Expect `.github/copilot-instructions.md`, `AGENTS.md`, and `CLAUDE.md`,
   with `.github/skills` and applicable `.claude/skills` available for task-specific work. If the
   task UI has no inventory, record that limitation; do not create a test task only to claim
   discovery.

The static check above keeps the current product catalog, runtime allowlist, image packaging, and
skill boundary aligned. Do not move or duplicate developer skill directories.

## Azure work

The intended handoff is simple: the human signs in with Azure CLI, selects the tenant and
subscription, and tells the coding agent to deploy per the [deployment guide](deployment.md). The
human names the instance, identity mode, and model configuration and explicitly authorizes apply.
The agent creates or updates the work record and handles the repository procedure, exact plan
confirmation, deployment, and verification.

```bash
az login --tenant '<tenant-id-or-domain>'
az account set --subscription '<subscription-id-or-name>'
az account show --query '{subscription:name,subscriptionId:id,tenantId:tenantId,user:user.name}' -o json
```

The agent may inspect Azure and run the repository's plan after confirming the selected account.
A plan-only request never permits deployment.

When the user explicitly requests deployment and the current plan matches the approved target, the
agent may use the exact confirmation printed by that plan.

Any new deletion, security decision, cost decision, or target change requires fresh approval. See
the [deployment guide](deployment.md) for the complete procedure.
