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
| Claude Code | `AGENTS.md`, then `CLAUDE.md` | `.claude/agents`, `.claude/skills`, and `.claude/settings.json` | That every developer has the optional PPEL or the same local permissions and models. |
| Codex | `AGENTS.md` | `.codex/skills` | That a locally configured profile, including PPEL, exists after a fresh clone. |
| GitHub Copilot CLI, VS Code agent mode, and Copilot cloud agent | `AGENTS.md` and `.github/copilot-instructions.md` | `.github/skills` and GitHub workflows | That custom instructions force a model to comply, or that every Copilot surface supports every optional GitHub feature. |

GitHub documents `.github/copilot-instructions.md` as the repository-wide Copilot instruction
location and `AGENTS.md` as agent guidance. GitHub also documents `.github/skills/<name>/SKILL.md`
for agent skills. We deliberately use those conventions and do not create a repository `.copilot/`
folder. See GitHub's [custom-instruction support reference](https://docs.github.com/en/copilot/reference/custom-instructions-support)
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
3. **Codex:** inspect its loaded instructions/context from the repository root, then inspect
   `.codex/skills`. Do not require a local profile.
4. **GitHub Copilot:** use `/instructions` and `/skills list` when that surface provides them.
   Verify `AGENTS.md`, thin `CLAUDE.md`, `.github/copilot-instructions.md`, and `.github/skills`.
   If the selected surface has no inventory command or Copilot CLI is absent, record that limitation
   rather than inferring discovery from a model answer.

When #47 moves the assistant package, update the current catalog path in this guide, the runtime
allowlist, container copy rule, and this static check in one change. Do not move or duplicate the
developer skill directories.

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
