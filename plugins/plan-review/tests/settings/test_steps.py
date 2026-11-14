"""The rules of a workflow, checked by name only."""

from plan_review.settings.steps import review_file, step_problems

WHERE = "harness.tool.workflow"


def test_a_required_agent_in_the_workflow_is_an_error() -> None:
    for name in ("architect", "grill-explorer"):
        [line] = step_problems(WHERE, [name])

        assert line.startswith(WHERE)
        assert name in line
        assert "required" in line
        assert "before the workflow" in line
        assert "leave it out" in line


def test_nothing_runs_at_the_same_time_as_the_implementer() -> None:
    [line] = step_problems(WHERE, [["implementer", "code-reviewer"]])

    assert "implementer" in line
    assert "nothing runs at the same time as the implementer" in line


def test_a_group_of_only_the_implementer_is_still_a_group() -> None:
    [line] = step_problems(WHERE, [["implementer"], "test-reviewer"])

    assert "nothing runs at the same time as the implementer" in line


def test_a_reviewer_before_the_implementer_waits_on_code_never_written() -> None:
    [line] = step_problems(WHERE, ["test-reviewer", "implementer"])

    assert "test-reviewer" in line
    assert "the implementer comes first" in line


def test_an_agent_listed_twice_is_an_error() -> None:
    [line] = step_problems(
        WHERE, ["implementer", "code-reviewer", ["code-reviewer", "test-reviewer"]]
    )

    assert "code-reviewer" in line
    assert "listed twice" in line


def test_a_fixed_step_in_the_workflow_is_an_unknown_step() -> None:
    [line] = step_problems(WHERE, ["implementer", "branch"])

    assert "branch always runs" in line
    assert "leave it out" in line


def test_a_good_workflow_has_no_problems() -> None:
    assert step_problems(WHERE, ["implementer", ["test-reviewer", "code-reviewer"]]) == []
    assert step_problems(WHERE, ["code-reviewer"]) == []


def test_review_files_keep_todays_names_and_custom_ones_get_their_own() -> None:
    assert review_file("test-reviewer") == "test-review.md"
    assert review_file("code-reviewer") == "code-review.md"
    assert review_file("security-reviewer") == "review-security-reviewer.md"
