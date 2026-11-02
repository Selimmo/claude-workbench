"""The agent definitions Claude Code loads from the plugin's agents/ folder."""

from pathlib import Path

import pytest

AGENTS = Path(__file__).parents[1] / "agents"
EDIT_TOOLS = {"Write", "Edit", "NotebookEdit"}


def frontmatter(name: str) -> dict[str, str]:
    text = (AGENTS / f"{name}.md").read_text()
    _, header, _ = text.split("---\n", 2)
    pairs = (line.split(":", 1) for line in header.splitlines() if line.strip())
    return {key.strip(): value.strip() for key, value in pairs}


def listed(value: str) -> set[str]:
    return {item.strip() for item in value.split(",") if item.strip()}


@pytest.mark.parametrize(
    ("name", "model"),
    [
        ("architect", "opus"),
        ("implementer", "sonnet"),
        ("test-reviewer", "opus"),
        ("code-reviewer", "opus"),
    ],
)
def test_each_agent_has_its_name_model_and_a_description(name: str, model: str) -> None:
    meta = frontmatter(name)

    assert meta["name"] == name
    assert meta["model"] == model
    assert len(meta["description"]) > 40


@pytest.mark.parametrize("name", ["test-reviewer", "code-reviewer"])
def test_reviewers_cannot_use_edit_tools(name: str) -> None:
    meta = frontmatter(name)

    assert listed(meta["disallowedTools"]) >= EDIT_TOOLS
    assert not EDIT_TOOLS & listed(meta["tools"])


@pytest.mark.parametrize("name", ["architect", "implementer", "test-reviewer", "code-reviewer"])
def test_no_agent_can_start_other_agents(name: str) -> None:
    # Only /ship orchestrates; an agent spawning agents would bypass the review loop.
    assert "Agent" in listed(frontmatter(name)["disallowedTools"])


@pytest.mark.parametrize("name", ["architect", "implementer", "test-reviewer", "code-reviewer"])
def test_agents_work_unchanged_when_copied_into_a_project(name: str) -> None:
    # ${CLAUDE_PLUGIN_ROOT} is only substituted for the plugin's own copy (#30).
    assert "${CLAUDE_PLUGIN_ROOT}" not in (AGENTS / f"{name}.md").read_text()
