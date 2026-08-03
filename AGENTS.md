# Repository agent entry point

This is the shared starting point for any developer agent working in CSA Workbench. Before changing
the repository, read [docs/README.md](docs/README.md) and
[docs/governance/README.md](docs/governance/README.md). Follow the documents named there:

- read the Master SDLC and Engineering Operating Standards before investigating or changing the
  repository;
- read the Testing Charter before designing, changing, or running checks; and
- read Agentic Design before changing agents, skills, prompts, tools, or handoffs.

Read the product, architecture, development, and deployment documents related to the requested
change. Stop and ask the user when required guidance is missing or contradictory. Preserve existing
worktree changes and do not switch the primary branch unless the user explicitly asks.

The canonical runtime-independence and skill-boundary policy is in
[Agentic Design](docs/governance/agentic-design.md). Do not duplicate shipped product skills into
developer skill directories.

## Native runtime additions

Shared repository policy has one home: `docs/governance/`. Native settings remain independent:

- Claude: `CLAUDE.md` and `.claude/`
- Codex: `.codex/`, with metadata-only `.agents/skills/` adapters for standalone discovery
- GitHub Copilot: `.github/copilot-instructions.md` and `.github/`

See [working with coding agents](docs/guides/coding-agents.md) for the supported surfaces and
smoke tests. A local profile or runtime-specific orchestration may add capabilities, but it never
replaces these repository rules.
