# Agentic design

Use this skill when changing coding agents, repository skills, prompts, tools, permissions,
delegation, or handoffs.

## Keep each runtime independent

Codex, Claude Code, and GitHub Copilot must each work from a fresh clone using their native files:

- Codex: `AGENTS.md`, `.codex/agents/`, and `.codex/skills/`
- Claude Code: `CLAUDE.md`, `.claude/agents/`, and `.claude/skills/`
- GitHub Copilot: `.github/copilot-instructions.md`, `.github/agents/`, and `.github/skills/`

Do not add a shared `.agents/` directory or make one runtime depend on another runtime's native
folder. The three native skill catalogs use matching names, and each `SKILL.md` points to one
document in `docs/repo-agent-skills/`.

## Keep repository and product skills separate

A repository-agent skill helps a coding agent investigate, implement, review, test, or deploy this
repository. It never ships with the application.

A product-assistant skill helps an end user complete a supported task inside CSA Workbench. Product
skills live in `backend/assistant/product-skills/`, are allowlisted by the assistant runtime, and
are packaged and evaluated as product behavior. Never copy them into a coding-agent skill folder.

## Use clear roles

The lead owns product intent, scope, architecture decisions, risk acceptance, final approval, and
communication with the user. Workers receive bounded assignments and return evidence.

| Responsibility | Claude Code | Codex |
|---|---|---|
| Lead and orchestration | `project-lead` | `project-lead` |
| Difficult analysis and independent review | `opus` | `sol` |
| Scoped implementation | `sonnet` | `terra` |
| Fast read-only investigation | `haiku` | `luna` |

GitHub Copilot provides a `project-lead` profile and may use its built-in workers. Do not invent
model-specific Copilot roles when the runtime does not require them.

Give each worker a goal, responsibility or file ownership, scope, exclusions, relevant sources,
required results, and stop conditions. A worker that changes files cannot independently approve
those changes. Do not ask a subagent to spawn another subagent when the runtime does not support it.

## Match permissions to responsibility

Use native permission or sandbox controls for technical enforcement. Prompts explain intent but do
not enforce a boundary. Investigators and independent reviewers should be read-only. Implementation
workers may write only within their assigned scope.

## Keep customer exports clean

The tracked native folders support repository developers. `.gitattributes` excludes `.claude/`,
`.codex/`, and `CLAUDE.md` from customer archives created with `git archive`.

Before finishing an agent change, confirm that every runtime can discover its entry point, matching
skills point to the same canonical documents, product skills remain separate, and obsolete or
duplicated instructions have been removed.
