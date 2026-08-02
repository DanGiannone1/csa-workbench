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

## Keep the two kinds of skills separate

- A **repository-agent workflow** helps a developer investigate, implement, review, test, or deploy
  this repository. It belongs only in a developer runtime's skill location, such as `.claude/skills`,
  `.codex/skills`, or `.github/skills`. It never ships in the application image.
- A **product-assistant skill** guides a CSA Workbench user through a supported product task. It
  lives in the product-assistant skill catalog, is allowlisted by the runtime, is packaged into the
  assistant image, and is versioned, hashed, and evaluated as product behavior. It must use typed
  product tools; it is not a developer-agent skill.

The catalog is currently `session-container/product-skills/`. The approved hierarchy work moves it
to `backend/assistant/product-skills/`; move its allowlist, packaging rule, and checks together.
Do not duplicate product skills into developer skill directories during that move.

## Native runtime additions

Shared repository policy has one home: `docs/governance/`. Native settings remain independent:

- Claude: `CLAUDE.md` and `.claude/`
- Codex: `.codex/`
- GitHub Copilot: `.github/copilot-instructions.md` and `.github/`

See [working with coding agents](docs/guides/coding-agents.md) for the supported surfaces and
smoke tests. A local profile or runtime-specific orchestration may add capabilities, but it never
replaces these repository rules.
