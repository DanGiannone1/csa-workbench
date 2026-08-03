# Repository agent entry point

Before working in this repository, read [docs/README.md](docs/README.md). Use the native repository
skills for the task:

- use `agentic-sdlc` and `engineering-operating-standards` before investigating or changing the
  repository;
- use `testing` before designing, changing, running, or reporting checks; and
- use `agentic-design` before changing agents, skills, prompts, tools, permissions, or handoffs.

The skills are lightweight pointers to the shared instructions in
[`docs/repo-agent-skills/`](docs/repo-agent-skills/README.md). Read the product, architecture,
development, and deployment documents related to the requested change.

Preserve existing worktree changes. Do not switch the primary branch, change Git hosting, deploy,
or affect external systems unless the user explicitly asks. Stop and ask when required guidance is
missing or contradictory.

Repository-agent skills never ship with the application. Product-assistant skills live only in
`backend/assistant/product-skills/`.
