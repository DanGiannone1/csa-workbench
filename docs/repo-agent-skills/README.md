# Repository-agent skills

These documents tell AI coding agents how to work in this repository. Each document has one small
pointer in the native skill folder for Codex, Claude Code, and GitHub Copilot.

| Skill | Use it for |
|---|---|
| [Agentic SDLC](agentic-sdlc.md) | Taking repository work from a request through review and completion |
| [Engineering operating standards](engineering-operating-standards.md) | Investigating and changing the repository safely |
| [Testing](testing.md) | Choosing and running checks locally or in Azure |
| [Agentic design](agentic-design.md) | Changing coding agents, skills, prompts, or handoffs |

These are development workflows. They do not ship with the application. Product-assistant skills
are separate and live in `backend/assistant/product-skills/`.

Keep the native `SKILL.md` files short. Put shared instructions here instead of copying them into
`.codex/skills/`, `.claude/skills/`, or `.github/skills/`.
