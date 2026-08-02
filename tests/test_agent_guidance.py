"""Static checks for developer-agent entry points and product-skill boundaries."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_SKILLS = ROOT / "session-container" / "product-skills"
DEVELOPER_SKILL_ROOTS = (ROOT / ".claude" / "skills", ROOT / ".codex" / "skills", ROOT / ".github" / "skills")
EXPECTED_PRODUCT_SKILLS = {"engagement-meeting-prep", "tasks", "calendar", "weekly-review"}


def text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_shared_and_native_entry_points_are_thin_and_linked() -> None:
    agents = text("AGENTS.md")
    claude = text("CLAUDE.md")
    copilot = text(".github/copilot-instructions.md")

    assert "docs/governance/" in agents
    assert "claude --agent" not in agents
    assert "codex --profile" not in agents
    assert claude.startswith("@AGENTS.md")
    assert "Follow the shared repository instructions in [AGENTS.md]" in copilot
    assert "Master SDLC" not in claude
    assert "Master SDLC" not in copilot
    assert not (ROOT / ".claude" / "settings.json").exists()


def test_product_skills_are_allowlisted_packaged_and_not_developer_skills() -> None:
    checked_in = {path.parent.name for path in PRODUCT_SKILLS.glob("*/SKILL.md")}
    assert checked_in == EXPECTED_PRODUCT_SKILLS

    runtime = text("session-container/skill_runtime.py")
    for skill in EXPECTED_PRODUCT_SKILLS:
        assert f'"{skill}"' in runtime
    assert "PRODUCT_SKILLS_ROOT" in runtime
    assert "FilesystemPermission" in runtime

    dockerfile = text("session-container/Dockerfile")
    assert "session-container/product-skills/ ./product-skills/" in dockerfile

    for developer_root in DEVELOPER_SKILL_ROOTS:
        duplicated = {path.parent.name for path in developer_root.glob("*/SKILL.md")} & EXPECTED_PRODUCT_SKILLS
        assert not duplicated, f"product skills must not be copied into {developer_root}: {sorted(duplicated)}"


def test_documented_skill_taxonomy_and_smoke_checks_have_one_destination() -> None:
    guide = text("docs/guides/coding-agents.md")
    assert "Supported developer-agent entry points" in guide
    assert "Discovery smoke tests" in guide
    assert ".copilot/" in guide
    policy = text("docs/governance/agentic-design.md")
    assert "backend/assistant/product-skills" in policy
    assert "Runtime independence and skill boundary" in policy
