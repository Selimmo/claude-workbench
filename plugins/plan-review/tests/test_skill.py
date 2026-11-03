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


def test_step_3_takes_a_whole_review_and_keeps_the_owner_posted() -> None:
    _, body = parts()

    assert "review_submitted" in body
    for stage in ["Review received", "Answering questions", "Architect revising", "--done"]:
        assert stage in body


def test_step_2_hands_straight_to_the_viewer_without_summarizing_the_plan() -> None:
    _, body = parts()
    step_2 = body.split("## 2. Plan", 1)[1].split("## 3.", 1)[0]

    assert "Don't summarize the plan" in step_2
    assert "summary lines" not in step_2


def test_a_review_sent_while_the_monitor_was_down_is_picked_up_after_re_arming() -> None:
    _, body = parts()
    step_3 = body.split("## 3. Review in the viewer", 1)[1].split("## 4.", 1)[0]

    assert "plan-review threads N" in step_3
    assert "no reply" in step_3
