"""The /ship skill's contract: who may start it, and what it must delegate."""

from pathlib import Path

import pytest

SKILL = Path(__file__).parents[1] / "skills" / "ship" / "SKILL.md"


def parts() -> tuple[dict[str, str], str]:
    _, header, body = SKILL.read_text().split("---\n", 2)
    pairs = (line.split(":", 1) for line in header.splitlines() if line.strip())
    return {k.strip(): v.strip() for k, v in pairs}, body


def test_ship_takes_an_issue_number_link_or_prompt() -> None:
    meta, _ = parts()

    assert meta["name"] == "ship"
    assert meta["disable-model-invocation"] == "true"  # side effects: branches, commits
    assert meta["argument-hint"].startswith("<issue number, issue link or prompt>")


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

    assert meta["argument-hint"] == ("<issue number, issue link or prompt> [--grill[=page|chat]]")
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

    assert "plan-review threads ID" in step_3
    assert "no reply" in step_3


def test_it_creates_the_work_folder_with_the_cli_before_anything_writes_there() -> None:
    _, body = parts()
    step_0 = body.split("## 0. Preconditions", 1)[1].split("## 1.", 1)[0]

    assert "plan-review init ID" in step_0


def _step_3() -> str:
    _, body = parts()
    return body.split("## 3. Review in the viewer", 1)[1].split("## 4.", 1)[0]


def test_an_approval_gets_a_status_before_moving_on() -> None:
    assert 'plan-review status ID "Approved, implementing"' in _step_3()


def test_a_review_already_being_handled_is_ignored() -> None:
    step_3 = _step_3()

    assert "already handled" in step_3
    assert "Resend" in step_3


def test_re_arming_also_checks_for_an_approval() -> None:
    step_3 = _step_3()

    assert "approved.json" in step_3
    assert "plan-review threads ID" in step_3
    assert "no reply" in step_3


def test_an_approval_found_on_re_arming_is_handled_like_an_approved_event() -> None:
    step_3 = _step_3()

    assert "handle it as `approved` below" in step_3
    assert "so go to step 4" not in step_3


def test_the_skill_calls_the_status_line_a_banner() -> None:
    assert "status line of what you are doing" not in _step_3()
    assert "banner" in _step_3()


def _step_0() -> str:
    _, body = parts()
    return body.split("## 0. Preconditions", 1)[1].split("## 1.", 1)[0]


def test_ship_reads_the_input_once_into_issue_md() -> None:
    step_0 = _step_0()

    for required in [
        "W/issue.md",
        "`#42`",
        "https://github.com/",
        "bare key",
        "plan-review init --prompt",
        "exactly as given",
        "paste",
    ]:
        assert required in step_0, required
    assert "as a prompt" in step_0  # the one-line stop for an unreadable issue


def test_the_grilling_covers_whatever_issue_md_describes() -> None:
    _, body = parts()
    step_1 = body.split("## 1.", 1)[1].split("## 2.", 1)[0]

    assert "W/issue.md" in step_1
    assert "issue N" not in step_1


def test_ship_never_writes_to_the_tracker() -> None:
    _, body = parts()
    step_7 = body.split("## 7.", 1)[1].split("## If something", 1)[0]

    for forbidden in ["gh issue comment", "gh issue close", "Closes #"]:
        assert forbidden not in body, forbidden
    assert "Refs #" in step_7
    assert "prompt run" in step_7
    assert "CLAUDE.md" in step_7


def test_ship_reads_the_serve_line_by_label() -> None:
    step_3 = _step_3()

    assert "plan-review: <label> at http://127.0.0.1:<port>/" in step_3
    assert "issue #N at" not in step_3


def _step_1() -> str:
    _, body = parts()
    return body.split("## 1.", 1)[1].split("## 2.", 1)[0]


def test_grill_mode_comes_from_the_flag_then_pipeline_then_preference_then_asking() -> None:
    step_1 = _step_1()

    for required in [
        "--grill=page",
        "--grill=chat",
        "plan-review prefs grill",
        "asks once",
        "plan-review prefs grill <mode>",
        "change it",
    ]:
        assert required in step_1, required
    for flag in ["--grill=page", "--grill=chat"]:
        assert flag in _step_0()  # step 0 reads the input without the flag


def test_page_grill_goes_through_the_helpers_and_keeps_the_banner_answered() -> None:
    step_1 = _step_1()

    for required in [
        "plan-review grill post",
        "plan-review grill pending",
        "plan-review grill decisions",
        "plan-review grill schema",
        "plan-review serve ID",
        "/grill",
        "Monitor",
        "catch up",
        "grill_submitted",
        "grill_confirmed",
        "grill_reopened",
        "plan-review status ID",
        "viewer.open",
        "`none`",
    ]:
        assert required in step_1, required


def test_page_grill_explains_other_answers_and_one_line_decisions() -> None:
    step_1 = _step_1()

    for required in [
        "`other`",
        "decision whose `question_id`",
        "never both",
        "`must_settle`",
        "to one line each",
    ]:
        assert required in step_1, required
    for gone in ["`own`", "`ask`", "asked back", "not yet"]:
        assert gone not in step_1, gone


def test_resume_and_the_chat_fallback_are_described() -> None:
    step_1 = _step_1()
    step_3 = _step_3()

    assert "confirmed" in step_1
    assert "skip to step 2" in step_1
    resume = step_1.split("you are resuming:")[1].split("Otherwise")[0]
    assert "plan-review serve ID" in resume  # nothing is running on a resume
    assert "serve` cannot start" in step_1
    assert "written by hand" in step_1
    assert "delete" in step_1  # the grill.json just posted
    assert "already running" in step_3
    assert 'plan-review status ID "Plan ready for review" --done' in step_3
