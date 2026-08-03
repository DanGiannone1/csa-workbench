"""Static checks for coding-agent entry points and skill boundaries."""

from __future__ import annotations

import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_SKILLS = ROOT / "docs" / "repo-agent-skills"
NATIVE_SKILL_ROOTS = (
    ROOT / ".codex" / "skills",
    ROOT / ".claude" / "skills",
    ROOT / ".github" / "skills",
)
PRODUCT_SKILLS = ROOT / "backend" / "assistant" / "product-skills"
EXPECTED_REPOSITORY_SKILLS = {
    "agentic-design",
    "agentic-sdlc",
    "engineering-operating-standards",
    "testing",
}
EXPECTED_PRODUCT_SKILLS = {"engagement-meeting-prep", "tasks", "calendar", "weekly-review"}


def text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def skill_names(root: Path) -> set[str]:
    return {path.parent.name for path in root.glob("*/SKILL.md")}


def test_entry_points_link_to_shared_repository_skills() -> None:
    agents = text("AGENTS.md")
    claude = text("CLAUDE.md")
    copilot = text(".github/copilot-instructions.md")

    assert "docs/repo-agent-skills/" in agents
    assert "docs/governance/" not in agents
    assert ".agents/" not in agents
    assert claude.startswith("@AGENTS.md")
    assert "claude --agent project-lead" in claude
    assert "PPEL" not in claude
    assert "[AGENTS.md]" in copilot
    assert "docs/repo-agent-skills/" in copilot
    assert not (ROOT / ".claude" / "settings.json").exists()


def test_native_skill_catalogs_are_matching_lightweight_pointers() -> None:
    canonical = {
        path.stem for path in CANONICAL_SKILLS.glob("*.md") if path.name != "README.md"
    }
    assert canonical == EXPECTED_REPOSITORY_SKILLS

    for native_root in NATIVE_SKILL_ROOTS:
        assert skill_names(native_root) == EXPECTED_REPOSITORY_SKILLS
        for name in EXPECTED_REPOSITORY_SKILLS:
            pointer = (native_root / name / "SKILL.md").read_text(encoding="utf-8")
            assert f"docs/repo-agent-skills/{name}.md" in pointer
            assert len(pointer.splitlines()) <= 10

    assert not (ROOT / ".agents").exists()
    assert not list((ROOT / ".codex" / "skills").glob("*/agents/openai.yaml"))
    assert not list((ROOT / ".claude" / "skills").glob("*/agents/openai.yaml"))


def test_native_agent_roles_are_clear_and_aligned() -> None:
    claude_agents = {path.stem for path in (ROOT / ".claude" / "agents").glob("*.md")}
    assert claude_agents == {"project-lead", "opus", "sonnet", "haiku"}
    assert "PPEL" not in "\n".join(
        path.read_text(encoding="utf-8") for path in (ROOT / ".claude" / "agents").glob("*.md")
    )
    assert "Agent(" not in text(".claude/agents/opus.md")

    expected_codex_models = {
        "project-lead": "gpt-5.6-sol",
        "sol": "gpt-5.6-sol",
        "terra": "gpt-5.6-terra",
        "luna": "gpt-5.6-luna",
    }
    codex_files = {path.stem: path for path in (ROOT / ".codex" / "agents").glob("*.toml")}
    assert set(codex_files) == set(expected_codex_models)
    for name, expected_model in expected_codex_models.items():
        profile = tomllib.loads(codex_files[name].read_text(encoding="utf-8"))
        assert profile["name"] == name
        assert profile["model"] == expected_model
        assert profile["description"]
        assert profile["developer_instructions"]

    assert (ROOT / ".github" / "agents" / "project-lead.agent.md").is_file()


def test_product_skills_are_allowlisted_packaged_and_separate() -> None:
    checked_in = skill_names(PRODUCT_SKILLS)
    assert checked_in == EXPECTED_PRODUCT_SKILLS

    runtime = text("backend/assistant/src/workbench_assistant/skill_runtime.py")
    for skill in EXPECTED_PRODUCT_SKILLS:
        assert f'"{skill}"' in runtime
    assert "PRODUCT_SKILLS_ROOT" in runtime
    assert "FilesystemPermission" in runtime

    dockerfile = text("backend/assistant/Dockerfile")
    assert "COPY backend/assistant/product-skills/ backend/assistant/product-skills/" in dockerfile

    for native_root in NATIVE_SKILL_ROOTS:
        duplicated = skill_names(native_root) & EXPECTED_PRODUCT_SKILLS
        assert not duplicated, f"product skills must not be copied into {native_root}: {sorted(duplicated)}"


def test_testing_skill_covers_local_and_azure_validation() -> None:
    testing = text("docs/repo-agent-skills/testing.md")
    assert "## Local application and browser testing" in testing
    assert "uv run python -m scripts.workbench eval playwright" in testing
    assert "## Azure testing" in testing
    assert "uv run python -m scripts.workbench deploy verify" in testing
    assert "deploy verify --browser" in testing
    assert not (ROOT / ".github" / "skills" / "localhost-ui-validation").exists()


def test_customer_archive_excludes_only_native_claude_and_codex_tooling() -> None:
    attributes = text(".gitattributes")
    assert "/.claude export-ignore" in attributes
    assert "/.codex export-ignore" in attributes
    assert "/CLAUDE.md export-ignore" in attributes
    assert "AGENTS.md export-ignore" not in attributes


def test_coding_agent_guide_explains_discovery_and_customer_export() -> None:
    guide = text("docs/guides/coding-agents.md")
    assert "Codex" in guide and "Claude Code" in guide and "GitHub Copilot" in guide
    assert "docs/repo-agent-skills/" in guide
    assert "git archive" in guide
    assert "PPEL" not in guide
    assert ".agents/" not in guide
