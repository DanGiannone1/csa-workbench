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

The repository supports a small, documented entry point for each runtime. All three use the same
shared policy in `docs/governance/`; their native files do not try to copy it.

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

## Skills: developer workflow or shipped product behavior?

| Kind | Purpose | Home | Ships? | How it is checked |
|---|---|---|---|---|
| Repository-agent workflow | Helps a developer work on this repository. | `.claude/skills`, `.codex/skills`, or `.github/skills` | No | Static guidance checks and the runtime's own discovery. |
| Product-assistant skill | Helps an end user complete an approved CSA Workbench task through typed product tools. | Current: `session-container/product-skills`; target after the hierarchy move: `backend/assistant/product-skills` | Yes | Runtime allowlist, image-content check, hash/version evidence, and product/Waza evals. |

Do not copy a product skill into a developer skill location for convenience. The two kinds have
different audiences, permissions, packaging, and evidence. The assistant runtime loads only its
approved product catalog; developer-agent guidance cannot expand that allowlist.

## Discovery smoke tests

Run these after changing an entry point or developer skill. They confirm discovery and references;
they do not claim that an instruction can technically enforce a runtime permission.

1. **Static check, every platform:** run `uv run --with pytest pytest tests/test_agent_guidance.py`
   from the repository root. It checks the entry-point links, product-skill allowlist, image
   packaging, and that product skills are not duplicated into developer skill folders.
2. **Claude Code:** start Claude Code in the repository root. Ask which file defines shared
   repository rules and confirm it identifies `AGENTS.md`; inspect the session's loaded references
   if the client shows them. Claude-native additions should be discoverable under `.claude/`.
3. **Codex:** start Codex in the repository root without assuming a local profile. Ask for the
   shared repository rules and confirm it identifies `AGENTS.md`; inspect `.codex/skills` for
   repository workflows. A profile is an optional local enhancement, not a smoke-test prerequisite.
4. **GitHub Copilot:** use one supported surface with the repository attached. Ask which repository
   instructions apply and inspect the response references when the surface provides them. Confirm
   `.github/copilot-instructions.md` and `AGENTS.md` are present, then verify a repository skill is
   under `.github/skills`. GitHub Copilot may combine applicable instruction files, so keep all
   shared rules in `AGENTS.md` and `docs/governance/`.

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
