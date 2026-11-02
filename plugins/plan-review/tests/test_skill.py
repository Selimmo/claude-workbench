"""The /ship skill's contract: who may start it, and what it must delegate."""

from pathlib import Path

import pytest

SKILL = Path(__file__).parents[1] / "skills" / "ship" / "SKILL.md"


def parts() -> tuple[dict[str, str], str]:
    _, header, body = SKILL.read_text().split("---\n", 2)
    pairs = (line.split(":", 1) for line in header.splitlines() if line.strip())
    return {k.strip(): v.strip() for k, v in pairs}, body


def test_only_the_owner_can_start_it_with_an_issue() -> None:
    meta, _ = parts()

    assert meta["name"] == "ship"
    assert meta["disable-model-invocation"] == "true"  # side effects: branches, commits
    assert meta["argument-hint"].startswith("<issue number or URL>")


@pytest.mark.parametrize(
    "required",
    [
        "plan-review:architect",
        "plan-review:implementer",
        "plan-review:test-reviewer",
        "plan-review:code-reviewer",
        "plan-review serve",
        "plan-review reply",
        "plan-review verdict",
        "plan-review tree-hash",
        "plan-review branch",
        "Monitor",
        "max_review_rounds",
    ],
)
def test_it_delegates_to_the_agents_and_deterministic_helpers(required: str) -> None:
    _, body = parts()

    assert required in body


def test_project_agents_take_precedence_over_the_plugins() -> None:
    _, body = parts()

    assert "`.claude/agents/<name>.md`" in body
    assert "otherwise `plan-review:<name>`" in body


def test_grilling_is_opt_in_and_the_hand_off_is_a_plain_file() -> None:
    meta, body = parts()

    assert meta["argument-hint"] == "<issue number or URL> [--grill]"
    assert "--no-grill" not in body  # never on by default
    for required in ["--grill", "`grilling` skill", "decisions.md", "github.com/mattpocock/skills"]:
        assert required in body
