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


def body_of(name: str) -> str:
    return (AGENTS / f"{name}.md").read_text()


@pytest.mark.parametrize("name", ["architect", "implementer", "test-reviewer", "code-reviewer"])
def test_no_agent_reads_the_issue_with_gh(name: str) -> None:
    # /ship reads the issue once, from any tracker, into issue.md; agents only read that file.
    assert "gh issue" not in body_of(name)


@pytest.mark.parametrize("name", ["architect", "code-reviewer"])
def test_the_agents_that_need_the_issue_read_issue_md(name: str) -> None:
    assert ".claude/work/<id>/issue.md" in body_of(name)


def test_the_architect_writes_criteria_for_a_prompt_and_the_reviewer_checks_them() -> None:
    architect, reviewer = body_of("architect"), body_of("code-reviewer")

    assert "acceptance_criteria" in architect
    assert "prompt" in architect
    assert "acceptance_criteria" in reviewer
    assert "issue.md" in reviewer


@pytest.mark.parametrize("name", ["architect", "implementer", "test-reviewer", "code-reviewer"])
def test_agents_find_their_files_by_run_id(name: str) -> None:
    text = body_of(name)

    assert ".claude/work/<id>/" in text
    assert ".claude/work/<issue>/" not in text


def test_the_architect_leaves_branch_out_of_the_plan() -> None:
    assert "leave `branch` out" in body_of("architect").lower()


def test_the_architect_writes_classes_in_the_new_shape() -> None:
    text = (AGENTS / "architect.md").read_text()

    for needle in ("`side`", "`name`", "`kind`", "`bases`", "`module`"):
        assert needle in text
    assert "keep every id" in text
    assert "old shape" in text or "written before" in text
