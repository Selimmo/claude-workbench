"""The /ship skill's contract: who may start it, and what it must delegate."""

from pathlib import Path

import pytest

from plan_review.harness.adapters import adapter_by_key
from plan_review.harness.workflow import load_workflow

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
        "plan-review launch",
        "plan-review config --harness claude-code",
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


def test_ship_no_longer_picks_project_agents_itself() -> None:
    _, body = parts()

    assert "use the project's own agent when" not in body
    assert "otherwise `plan-review:<name>`" not in body
    assert "Never choose the agent, model or effort yourself" in body
    assert "plan-review launch <name> --harness claude-code" in body


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
    step_7 = body.split("## 6.", 1)[1].split("## If something", 1)[0]

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
        "ask the owner once",
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

    assert "`other`" in step_1  # the explorer settles or replies to it: see its own text
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
    assert "carry on in chat mode with the same `W/grill.json`" in step_1
    assert "already running" in step_3
    assert 'plan-review status ID "Plan ready for review" --done' in step_3


def test_the_skill_uses_the_new_folder_and_config_file() -> None:
    _, body = parts()

    assert "`.plan-review/work/ID/`" in body
    assert "`.plan-review/config.json`" in body
    assert ".claude/work" not in body
    assert "pipeline.json" not in body


def test_an_old_file_hint_is_passed_on_to_the_owner() -> None:
    assert "Show the owner each line it printed on stderr" in _step_0()
    assert "line about moving an old file" in _step_0()


def test_claude_code_ship_keeps_its_waiting_text() -> None:
    _, body = parts()

    assert "Monitor" in body
    assert "run_in_background" in body
    assert "arm it again" in body
    assert "plan-review wait" not in body
    assert "--detach" not in body


# --- config, launch, groups and the grill explorer (#66) ---------------------------------------

PLUGIN = SKILL.parents[2]


def generated_ship(key: str) -> str:
    harness = adapter_by_key(key)
    assert harness is not None
    files = harness.files(load_workflow(PLUGIN / "workflow"))
    return next(text for path, text in files.items() if "ship" in path.as_posix().lower())


def generated_agents(key: str) -> dict[str, str]:
    harness = adapter_by_key(key)
    assert harness is not None
    files = harness.files(load_workflow(PLUGIN / "workflow"))
    return {path.name: text for path, text in files.items() if "agents/" in path.as_posix()}


TOOLS = ["claude-code", "codex", "opencode"]


@pytest.mark.parametrize("key", TOOLS)
def test_the_generated_texts_name_their_tool_for_config_and_launch(key: str) -> None:
    harness = adapter_by_key(key)
    assert harness is not None
    ship = generated_ship(key)

    assert harness.slots()["harness"] == key
    assert f"plan-review config --harness {key}" in ship
    assert f"plan-review launch <name> --harness {key}" in ship
    for name, text in generated_agents(key).items():
        if any(role in name for role in ("architect", "implementer", "reviewer")):
            assert f"plan-review config --harness {key}" in text, name


START_AGENT = {
    "claude-code": ["Agent tool", "`subagent_type`", "`model`", "`effort`"],
    "codex": [
        "`spawn_agent`",
        "`agent_type`",
        '`fork_turns` is `"none"`',
        "`reasoning_effort`",
        "`task_name`",
        "lowercase letters, digits and underscores",
        "`code_reviewer`",
        "not a model or effort refusal",
    ],
    "opencode": ["`subagent` tool", "`agent`", "`<model>#<effort>`"],
}


@pytest.mark.parametrize("key", TOOLS)
def test_each_ship_starts_an_agent_with_its_tools_model_and_effort_parameters(key: str) -> None:
    ship = generated_ship(key)

    for needle in START_AGENT[key]:
        assert needle in ship, needle
    assert "leave it out" in ship  # a null model or effort


TOGETHER = {
    "claude-code": ["one Agent call per reviewer", "in the same message"],
    "codex": [
        "`wait_agent`",
        "`timeout_ms`",
        "until every one is final",
        "all `spawn_agent` calls of the group in one single turn, before any wait",
    ],
    "opencode": ["one `subagent` call per agent", "in the same message"],
}


@pytest.mark.parametrize("key", TOOLS)
def test_each_ship_starts_a_group_together_and_waits_for_all(key: str) -> None:
    ship = generated_ship(key)

    for needle in TOGETHER[key]:
        assert needle in ship, needle


@pytest.mark.parametrize("key", TOOLS)
def test_ship_falls_back_to_the_session_when_a_model_or_effort_is_refused(key: str) -> None:
    ship = generated_ship(key)

    assert "start the same agent again without `model` and `effort`" in ship
    assert "runs on the session's model: <the tool's error>" in ship
    assert "don't wait on it" in ship


def test_codex_ship_says_to_trust_the_project_for_an_unknown_agent() -> None:
    assert "only in a trusted project" in generated_ship("codex")
    for key in ("claude-code", "opencode"):
        assert "trusted project" not in generated_ship(key)
        assert "agent file is missing" in generated_ship(key)


def test_ship_checks_the_config_before_anything_and_passes_its_lines_on() -> None:
    step_0 = _step_0()

    assert step_0.index("plan-review config --harness claude-code") < step_0.index("git status")
    assert "show the errors and stop" in step_0
    assert "each line it printed on stderr, once" in step_0
    assert "never committed" in step_0
    assert ".plan-review/.gitignore" in step_0
    assert "already commits" in step_0
    assert "ask the owner to commit it" in step_0
    assert "`replace`" in step_0
    assert "`.claude/agents/<name>.md` in the project, or `~/.claude/agents/<name>.md`" in step_0


def _step_5() -> str:
    _, body = parts()
    return body.split("## 5.", 1)[1].split("## 6.", 1)[0]


def test_ship_runs_each_stage_with_one_combined_fix_round() -> None:
    step_5 = _step_5()

    for needle in (
        "settings.harness.claude-code.workflow",
        "a list is a group of reviewers that run at the same time",
        "`before=$(plan-review tree-hash)`",
        "`after=$(plan-review tree-hash)`",
        "`W/<review>`",
        "plan-review verdict W/<review>",
        "one **combined fix round**",
        "every FINDINGS file of the stage at once",
        "the whole stage runs again",
        "counts as one round against `max`",
    ):
        assert needle in step_5, needle


def test_ship_writes_the_code_itself_when_the_implementer_is_removed() -> None:
    step_5 = _step_5()

    assert "`main_session` is true" in step_5
    assert "read the file `instructions` names" in step_5
    assert "same `tdd` setting" in step_5
    assert "W/impl-report.md" in step_5


def test_grill_runs_through_a_fresh_grill_explorer_each_round() -> None:
    step_1 = _step_1()

    assert "plan-review launch" in parts()[1]
    assert 'Start the explorer (see "Starting an agent": the name is `grill-explorer`)' in step_1
    assert "Grill round. Run ID. Mode page." in step_1
    assert "You never load a grilling skill yourself" in step_1
    assert "Skill tool" not in step_1
    for command in ("grill answer ID W/grill-answers.json", "grill confirm ID", "grill reopen ID"):
        assert f"plan-review {command}" in step_1
    assert "plan-review grill decisions ID" in step_1
    assert "a new explorer" in step_1
