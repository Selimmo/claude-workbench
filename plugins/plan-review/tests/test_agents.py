"""The agent definitions Claude Code loads from the plugin's agents/ folder."""

import hashlib
import tomllib
from pathlib import Path

import pytest

AGENTS = Path(__file__).parents[1] / "agents"
EDIT_TOOLS = {"Write", "Edit", "NotebookEdit"}
ALL = ["grill-explorer", "architect", "implementer", "test-reviewer", "code-reviewer"]


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
        ("grill-explorer", "opus"),
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


@pytest.mark.parametrize("name", ALL)
def test_no_agent_can_start_other_agents(name: str) -> None:
    # Only /ship orchestrates; an agent spawning agents would bypass the review loop.
    assert "Agent" in listed(frontmatter(name)["disallowedTools"])


@pytest.mark.parametrize("name", ALL)
def test_agents_work_unchanged_when_copied_into_a_project(name: str) -> None:
    # ${CLAUDE_PLUGIN_ROOT} is only substituted for the plugin's own copy (#30).
    assert "${CLAUDE_PLUGIN_ROOT}" not in (AGENTS / f"{name}.md").read_text()


def body_of(name: str) -> str:
    return (AGENTS / f"{name}.md").read_text()


@pytest.mark.parametrize("name", ALL)
def test_no_agent_reads_the_issue_with_gh(name: str) -> None:
    # /ship reads the issue once, from any tracker, into issue.md; agents only read that file.
    assert "gh issue" not in body_of(name)


@pytest.mark.parametrize("name", ["grill-explorer", "architect", "code-reviewer"])
def test_the_agents_that_need_the_issue_read_issue_md(name: str) -> None:
    assert ".plan-review/work/<id>/issue.md" in body_of(name)


def test_the_architect_writes_criteria_for_a_prompt_and_the_reviewer_checks_them() -> None:
    architect, reviewer = body_of("architect"), body_of("code-reviewer")

    assert "acceptance_criteria" in architect
    assert "prompt" in architect
    assert "acceptance_criteria" in reviewer
    assert "issue.md" in reviewer


@pytest.mark.parametrize("name", ALL)
def test_agents_find_their_files_by_run_id(name: str) -> None:
    text = body_of(name)

    assert ".plan-review/work/<id>/" in text
    assert ".plan-review/work/<issue>/" not in text


def test_the_architect_leaves_branch_out_of_the_plan() -> None:
    assert "leave `branch` out" in body_of("architect").lower()


def test_the_architect_writes_classes_in_the_new_shape() -> None:
    text = (AGENTS / "architect.md").read_text()

    for needle in ("`side`", "`name`", "`kind`", "`bases`", "`module`"):
        assert needle in text
    assert "keep every id" in text
    assert "old shape" in text or "written before" in text


def test_the_implementer_may_not_edit_the_run_folder_except_its_report() -> None:
    text = body_of("implementer")

    assert "edit anything under `.claude/`, or under `.plan-review/` except your report" in text


def test_every_tool_gets_a_grill_explorer_that_can_write_its_turn_but_not_edit() -> None:
    meta = frontmatter("grill-explorer")

    assert listed(meta["tools"]) == {"Read", "Grep", "Glob", "Bash", "Write"}
    assert listed(meta["disallowedTools"]) == {"Edit", "NotebookEdit", "Agent"}
    assert meta["model"] == "opus"
    assert meta["effort"] == "high"


PLUGIN = Path(__file__).parents[1]
SOURCE = PLUGIN / "workflow" / "agents" / "grill-explorer.md"
OPENCODE = PLUGIN / "src" / "plan_review" / "harness" / "adapters" / "opencode_files" / "agents"
CODEX = PLUGIN / "src" / "plan_review" / "harness" / "adapters" / "codex_files" / "agents"
OURS = "## How plan-review runs this"
# The skill's body after its frontmatter at commit 5863806, stripped at both ends.
SKILL_SHA256 = "af13c9f244f2a2179be4823bb76e808ccac1652cbb5d15abbff3f4925deb9472"
NOTICE = (
    "Copyright (c) 2026 Matt Pocock",
    "Permission is hereby granted, free of charge, to any person obtaining a copy",
    'THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND',
)


def copied_text(text: str) -> str:
    """The slice from the skill's first words up to our own section, stripped."""
    return text.split("Interview the user relentlessly", 1)[1].split(OURS, 1)[0]


def skill_hash(text: str) -> str:
    slice_ = ("Interview the user relentlessly" + copied_text(text)).strip()
    return hashlib.sha256(slice_.encode()).hexdigest()


def generated_explorers() -> dict[str, str]:
    toml = tomllib.loads((CODEX / "plan-review-grill-explorer.toml").read_text("utf-8"))
    return {
        "claude": (AGENTS / "grill-explorer.md").read_text("utf-8"),
        "opencode": (OPENCODE / "plan-review-grill-explorer.md").read_text("utf-8"),
        "codex": toml["developer_instructions"],
    }


def test_the_grill_explorer_carries_the_grilling_skill_word_for_word() -> None:
    source = SOURCE.read_text("utf-8")
    source_line = (
        "https://github.com/mattpocock/skills/blob/5863806dd4e15c63174bee4e7515a4256792ecfa"
        "/skills/productivity/grilling/SKILL.md"
    )

    assert source_line in source
    assert source.index(NOTICE[0]) < source.index("Interview the user relentlessly")
    for line in NOTICE:
        assert line in source
    assert skill_hash(source) == SKILL_SHA256
    for text in generated_explorers().values():
        for line in NOTICE:
            assert line in text
        assert skill_hash(text) == SKILL_SHA256


def test_the_grill_explorer_posts_turns_and_keeps_notes() -> None:
    ours = SOURCE.read_text("utf-8").split(OURS, 1)[1]

    for needle in (
        "grill.json",
        "grill-notes.md",
        "plan-review grill post",
        "W/grill-turn.json",
        "look up facts yourself",
        "you can't start another agent",
        "must_settle",
        "three replies have already gone out",
        "done: true",
        "Don't wait for answers",
    ):
        assert needle.lower() in ours.lower()


def source(name: str) -> str:
    return (PLUGIN / "workflow" / "agents" / f"{name}.md").read_text("utf-8")


@pytest.mark.parametrize("name", ["architect", "implementer", "test-reviewer", "code-reviewer"])
def test_the_agents_read_the_config_for_their_own_tool(name: str) -> None:
    assert "plan-review config --harness {{harness}}" in source(name)
    assert "plan-review config`" not in source(name)


def test_the_implementer_and_test_reviewer_follow_the_tdd_setting() -> None:
    implementer, reviewer = source("implementer"), source("test-reviewer")

    assert "`settings.tdd`" in implementer
    assert "test-first" in implementer
    assert "not test-first" in implementer  # what its red column says when tdd is off
    assert "`settings.tdd`" in reviewer
    assert "skip" in reviewer.lower()
    assert "test-first" in reviewer


def test_the_implementer_fixes_every_review_file_of_a_later_round() -> None:
    assert "fix every finding in every review file" in source("implementer")


def test_mutation_testing_is_off_unless_the_config_turns_it_on() -> None:
    text = source("test-reviewer")

    for needle in (
        "only when `settings.mutation` is set",
        "If `settings.mutation` is not set",
        "make no copy and no breaks",
        "read the tests only",
    ):
        assert needle in text, needle


def test_the_test_reviewer_does_mutation_testing_on_a_throwaway_copy() -> None:
    text = source("test-reviewer")

    for needle in (
        "Mutation testing",
        "new folder in the system temp folder",
        "only on the lines this change added or changed",
        "at most 20 breaks",
        "about 10 minutes",
        "stopped early",
        "no test caught",
        "Never use `git worktree` or `git stash`",
        "write only there",
        '`settings.mutation` is `"agent"`',
    ):
        assert needle in text, needle


def test_the_test_reviewer_runs_the_configured_mutation_tool_on_the_copy() -> None:
    text = source("test-reviewer")

    for needle in (
        "`settings.mutation`",
        "inside the copy",
        "time limit of about 10 minutes",
        "exits with an error code",
        "read the output anyway",
        "surviving break",
        "could not start",
        "ran out of time with nothing to show",
        "break lines by hand",
        "any other string",
    ):
        assert needle in text, needle


def test_the_architect_and_the_grill_explorer_put_code_and_paths_in_backticks() -> None:
    architect = source("architect").lower()
    ours = SOURCE.read_text("utf-8").split(OURS, 1)[1].lower()

    assert "code and file paths" in architect and "in backticks" in architect
    assert "code and file paths" in ours and "in backticks" in ours


def test_the_architect_writes_notes_in_plain_words_for_the_owner() -> None:
    text = source("architect")

    for needle in (
        "read by the owner",
        "one or two plain sentences",
        "at most 300 characters",
        "plan-review validate",
        "No CSS, selectors",
        "The summary is plain words too",
        "may stay one short paragraph",
        "ARIA",
        "files",
    ):
        assert needle in text, needle


@pytest.mark.parametrize("name", ["implementer", "test-reviewer", "code-reviewer"])
def test_the_agents_run_plan_review_from_the_project_root(name: str) -> None:
    assert "from the project root" in source(name), name
