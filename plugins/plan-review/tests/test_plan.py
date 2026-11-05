import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from plan_review.plan import Plan, PlanFileError, load_plan, record_branch

ISSUE = {"id": "7", "kind": "issue", "title": "Add hints"}


def minimal(**extra: Any) -> dict[str, Any]:
    return {"issue": ISSUE, "summary": "Hint button.", **extra}


def test_minimal_plan_parses_with_empty_sections() -> None:
    plan = Plan.model_validate(minimal())

    assert plan.issue.id == "7"
    assert plan.classes == []
    assert plan.architecture is None


def test_an_issue_block_has_a_text_id_and_a_kind() -> None:
    key = Plan.model_validate(minimal(issue={"id": "PROJ-123", "kind": "issue", "title": "t"}))
    prompt = Plan.model_validate(
        minimal(
            issue={"id": "add-dark-mode-2026-11-05", "kind": "prompt", "title": "t"},
            acceptance_criteria=["Dark mode toggles"],
        )
    )

    assert (key.issue.id, key.issue.kind) == ("PROJ-123", "issue")
    assert (prompt.issue.id, prompt.issue.kind) == ("add-dark-mode-2026-11-05", "prompt")
    with pytest.raises(ValidationError, match=r"issue\.kind"):
        Plan.model_validate(minimal(issue={"id": "7", "title": "t"}))


SESSION_STORE = {
    "id": "class:SessionStore",
    "name": "SessionStore",
    "kind": "class",
    "status": "modified",
    "members": [
        {
            "id": "class:SessionStore.save",
            "signature": "save(s: Session) -> None",
            "status": "added",
        }
    ],
}


def test_class_has_kind_status_and_members_with_their_own_status() -> None:
    plan = Plan.model_validate(minimal(classes=[SESSION_STORE]))

    store = plan.classes[0]
    assert (store.name, store.kind, store.status) == ("SessionStore", "class", "modified")
    assert store.members[0].signature == "save(s: Session) -> None"
    assert store.members[0].status == "added"


def test_unknown_field_is_rejected_so_typos_are_caught() -> None:
    with pytest.raises(ValidationError, match="stauts"):
        Plan.model_validate(minimal(classes=[{**SESSION_STORE, "stauts": "added"}]))


SESSION = {"id": "class:Session", "name": "Session", "kind": "dataclass", "status": "unchanged"}
STORES = {
    "id": "rel:store-session",
    "from": "class:SessionStore",
    "to": "class:Session",
    "kind": "uses",
    "status": "added",
}


def test_relation_links_two_classes() -> None:
    plan = Plan.model_validate(minimal(classes=[SESSION_STORE, SESSION], relations=[STORES]))

    rel = plan.relations[0]
    assert (rel.source, rel.target, rel.kind, rel.status) == (
        "class:SessionStore",
        "class:Session",
        "uses",
        "added",
    )


def test_relation_to_unknown_class_is_rejected_naming_both_ids() -> None:
    with pytest.raises(ValidationError, match="rel:store-session.*class:Session"):
        Plan.model_validate(minimal(classes=[SESSION_STORE], relations=[STORES]))


HINT_SEQUENCE = {
    "id": "flow:hint",
    "title": "Hint request",
    "kind": "sequence",
    "participants": [
        {"id": "flow:hint/client", "name": "Client", "status": "unchanged"},
        {"id": "flow:hint/agent", "name": "Agent", "status": "unchanged"},
    ],
    "steps": [
        {
            "id": "flow:hint/1",
            "from": "flow:hint/client",
            "to": "flow:hint/agent",
            "label": "request_hint",
            "status": "added",
        }
    ],
}


def test_sequence_flow_has_participants_and_ordered_labelled_steps() -> None:
    plan = Plan.model_validate(minimal(flows=[HINT_SEQUENCE]))

    flow = plan.flows[0]
    assert flow.kind == "sequence"
    assert [p.name for p in flow.participants] == ["Client", "Agent"]
    assert flow.steps[0].label == "request_hint"


GRADING_FLOWCHART = {
    "id": "flow:grade",
    "title": "Grading",
    "kind": "flowchart",
    "nodes": [
        {"id": "flow:grade/start", "name": "Answer received", "status": "unchanged"},
        {"id": "flow:grade/score", "name": "Score answer", "status": "added"},
    ],
    "edges": [
        {
            "id": "flow:grade/e1",
            "from": "flow:grade/start",
            "to": "flow:grade/score",
            "status": "added",
        }
    ],
}


def test_flowchart_flow_has_nodes_and_edges() -> None:
    plan = Plan.model_validate(minimal(flows=[HINT_SEQUENCE, GRADING_FLOWCHART]))

    chart = plan.flows[1]
    assert chart.kind == "flowchart"
    assert [n.name for n in chart.nodes] == ["Answer received", "Score answer"]
    assert chart.edges[0].label is None


def test_sequence_step_to_unknown_participant_is_rejected() -> None:
    bad = {**HINT_SEQUENCE, "participants": HINT_SEQUENCE["participants"][:1]}

    with pytest.raises(ValidationError, match="flow:hint/1.*flow:hint/agent"):
        Plan.model_validate(minimal(flows=[bad]))


def test_flowchart_edge_to_unknown_node_is_rejected() -> None:
    bad = {**GRADING_FLOWCHART, "nodes": GRADING_FLOWCHART["nodes"][:1]}

    with pytest.raises(ValidationError, match="flow:grade/e1.*flow:grade/score"):
        Plan.model_validate(minimal(flows=[bad]))


ARCHITECTURE = {
    "nodes": [
        {"id": "arch:web", "name": "Web client", "kind": "client", "status": "unchanged"},
        {"id": "arch:agent", "name": "Agent worker", "kind": "service", "status": "modified"},
    ],
    "edges": [
        {
            "id": "arch:web-agent",
            "from": "arch:web",
            "to": "arch:agent",
            "label": "LiveKit",
            "status": "unchanged",
        }
    ],
}


def test_architecture_has_kinded_nodes_and_labelled_edges() -> None:
    plan = Plan.model_validate(minimal(architecture=ARCHITECTURE))

    assert plan.architecture is not None
    assert [n.kind for n in plan.architecture.nodes] == ["client", "service"]
    assert plan.architecture.edges[0].label == "LiveKit"


def test_architecture_edge_to_unknown_node_is_rejected() -> None:
    bad = {**ARCHITECTURE, "nodes": ARCHITECTURE["nodes"][:1]}

    with pytest.raises(ValidationError, match="arch:web-agent.*arch:agent"):
        Plan.model_validate(minimal(architecture=bad))


FILE = {
    "id": "file:store",
    "path": "backend/src/store.py",
    "kind": "code",
    "change": "modified",
    "reason": "Add save()",
}
TEST = {
    "id": "test:1",
    "name": "test_save_persists_session",
    "target": "class:SessionStore.save",
    "behaviour": "A saved session can be read back",
}
RISK = {
    "id": "risk:1",
    "kind": "question",
    "text": "Should save() overwrite?",
    "severity": "medium",
}


def test_files_tests_and_risks_parse() -> None:
    plan = Plan.model_validate(
        minimal(classes=[SESSION_STORE], files=[FILE], tests=[TEST], risks=[RISK])
    )

    assert (plan.files[0].kind, plan.files[0].change) == ("code", "modified")
    assert plan.tests[0].target == "class:SessionStore.save"
    assert (plan.risks[0].kind, plan.risks[0].mitigation) == ("question", None)


def test_test_targeting_unknown_element_is_rejected() -> None:
    with pytest.raises(ValidationError, match="test:1.*class:SessionStore.save"):
        Plan.model_validate(minimal(tests=[TEST]))


def test_duplicate_ids_anywhere_in_the_plan_are_rejected() -> None:
    clash = {**RISK, "id": "class:SessionStore"}

    with pytest.raises(ValidationError, match="duplicate id 'class:SessionStore'"):
        Plan.model_validate(minimal(classes=[SESSION_STORE], risks=[clash]))


def test_issue_may_link_to_its_url() -> None:
    url = "https://github.com/o/r/issues/7"
    plan = Plan.model_validate(minimal(issue={**ISSUE, "url": url}))

    assert plan.issue.url == url


EXAMPLE = Path(__file__).parents[1] / "examples" / "plan.json"
PROMPT_EXAMPLE = Path(__file__).parents[1] / "examples" / "prompt-plan.json"


def test_example_plan_is_valid_and_uses_every_section_and_flow_kind() -> None:
    plan = Plan.model_validate_json(EXAMPLE.read_text())

    assert plan.issue.url
    assert all([plan.classes, plan.relations, plan.architecture, plan.files, plan.tests])
    assert {f.kind for f in plan.flows} == {"sequence", "flowchart"}
    assert {r.kind for r in plan.risks} == {"risk", "question"}
    assert {c.status for c in plan.classes} >= {"added", "modified", "unchanged"}


def test_both_example_plans_are_valid() -> None:
    # The page tests read these raw, so they must already use the current issue block.
    issue_plan = json.loads(EXAMPLE.read_text())
    prompt_plan = json.loads(PROMPT_EXAMPLE.read_text())

    assert issue_plan["issue"]["id"] == "42"
    assert issue_plan["issue"]["kind"] == "issue"
    assert "number" not in issue_plan["issue"]
    prompt = Plan.model_validate(prompt_plan)
    assert prompt.issue.kind == "prompt"
    assert prompt.acceptance_criteria
    assert prompt.branch == prompt.issue.id


@pytest.mark.parametrize("bad", ["#42", "a/b"])
def test_an_issue_id_that_is_not_a_run_id_is_rejected(bad: str) -> None:
    with pytest.raises(ValidationError) as error:
        Plan.model_validate(minimal(issue={**ISSUE, "id": bad}))

    assert error.value.errors()[0]["loc"] == ("issue", "id")
    assert "invalid run id" in str(error.value)


def test_an_old_plan_with_an_issue_number_still_loads() -> None:
    plan = Plan.model_validate(minimal(issue={"number": 42, "title": "t"}))

    assert (plan.issue.id, plan.issue.kind) == ("42", "issue")
    assert "number" not in Plan.model_json_schema()["$defs"]["Issue"]["properties"]


@pytest.mark.parametrize("bad", ["seven", True, 4.5])
def test_an_old_issue_number_that_is_not_an_integer_is_an_error(bad: object) -> None:
    with pytest.raises(ValidationError) as error:
        Plan.model_validate(minimal(issue={"number": bad, "title": "t"}))

    (problem,) = error.value.errors()
    assert problem["loc"] == ("issue",)
    assert "'number' must be a whole number" in problem["msg"]


PROMPT = {"id": "add-dark-mode-2026-11-05", "kind": "prompt", "title": "Add dark mode"}


@pytest.mark.parametrize("criteria", [None, []])
def test_a_prompt_plan_must_list_its_acceptance_criteria(criteria: list[str] | None) -> None:
    extra = {} if criteria is None else {"acceptance_criteria": criteria}

    with pytest.raises(ValidationError) as error:
        Plan.model_validate(minimal(issue=PROMPT, **extra))

    assert "a prompt plan must list its acceptance criteria" in str(error.value)


def test_an_issue_plan_may_or_may_not_list_acceptance_criteria() -> None:
    assert Plan.model_validate(minimal()).acceptance_criteria == []
    assert Plan.model_validate(minimal(acceptance_criteria=["A"])).acceptance_criteria == ["A"]


def test_each_acceptance_criterion_is_a_commentable_element() -> None:
    plan = Plan.model_validate(minimal(acceptance_criteria=["A", "B"], classes=[SESSION]))
    ids = plan.element_ids()

    assert ids[:2] == ["criterion:1", "criterion:2"]
    assert ids.index("criterion:2") < ids.index("class:Session")
    targeted = minimal(
        acceptance_criteria=["A", "B"],
        tests=[{"id": "test:1", "name": "t", "target": "criterion:2", "behaviour": "b"}],
    )
    assert Plan.model_validate(targeted).tests[0].target == "criterion:2"
    shrunk = Plan.model_validate(minimal(acceptance_criteria=["A"]))
    assert "criterion:2" not in shrunk.element_ids()


def test_a_plan_may_record_its_branch() -> None:
    assert Plan.model_validate(minimal()).branch is None
    assert Plan.model_validate(minimal(branch="feat/7-add-hints")).branch == "feat/7-add-hints"


def test_recording_the_branch_keeps_the_plan_as_written(tmp_path: Path) -> None:
    path = tmp_path / "plan.json"
    old = {"issue": {"number": 7, "title": "Add hints"}, "summary": "Hint button."}
    path.write_text(json.dumps(old))

    record_branch(path, "feat/7-add-hints")

    assert json.loads(path.read_text()) == {**old, "branch": "feat/7-add-hints"}
    assert load_plan(path).branch == "feat/7-add-hints"


@pytest.mark.parametrize("extra", [{"id": "PROJ-1"}, {"kind": "prompt"}])
def test_an_old_issue_number_beside_id_or_kind_is_an_error(extra: dict[str, str]) -> None:
    with pytest.raises(ValidationError) as error:
        Plan.model_validate(minimal(issue={"number": 7, "title": "t", **extra}))

    (problem,) = error.value.errors()
    assert problem["loc"] == ("issue",)
    assert "'number'" in problem["msg"]


def test_recording_the_branch_keeps_non_ascii_text_readable(tmp_path: Path) -> None:
    path = tmp_path / "plan.json"
    path.write_text(json.dumps({"summary": "red → green"}, ensure_ascii=False), encoding="utf-8")

    record_branch(path, "feat/x")

    assert "red → green" in path.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("content", "first_line"),
    [
        (b"{bad", "Invalid JSON: key must be a string at line 1 column 2"),
        (b"{}", "issue: Field required"),
        (b"\xff\xfe", "Invalid JSON"),
    ],
)
def test_load_plan_names_the_file_in_every_error_line(
    tmp_path: Path, content: bytes, first_line: str
) -> None:
    path = tmp_path / "plan.json"
    path.write_bytes(content)

    with pytest.raises(PlanFileError) as error:
        load_plan(path)

    assert error.value.errors[0].startswith(f"{path.as_posix()}: {first_line}")
    assert all(line.startswith(f"{path.as_posix()}: ") for line in error.value.errors)


def test_a_missing_plan_names_the_file_once(tmp_path: Path) -> None:
    with pytest.raises(PlanFileError) as error:
        load_plan(tmp_path / "plan.json")

    assert error.value.errors == [f"{(tmp_path / 'plan.json').as_posix()}: file not found"]
