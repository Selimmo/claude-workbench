from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from plan_review.plan import Plan


def minimal(**extra: Any) -> dict[str, Any]:
    return {"issue": {"number": 7, "title": "Add hints"}, "summary": "Hint button.", **extra}


def test_minimal_plan_parses_with_empty_sections() -> None:
    plan = Plan.model_validate(minimal())

    assert plan.issue.number == 7
    assert plan.classes == []
    assert plan.architecture is None


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
    plan = Plan.model_validate(minimal(issue={"number": 7, "title": "Add hints", "url": url}))

    assert plan.issue.url == url


EXAMPLE = Path(__file__).parents[1] / "examples" / "plan.json"


def test_example_plan_is_valid_and_uses_every_section_and_flow_kind() -> None:
    plan = Plan.model_validate_json(EXAMPLE.read_text())

    assert plan.issue.url
    assert all([plan.classes, plan.relations, plan.architecture, plan.files, plan.tests])
    assert {f.kind for f in plan.flows} == {"sequence", "flowchart"}
    assert {r.kind for r in plan.risks} == {"risk", "question"}
    assert {c.status for c in plan.classes} >= {"added", "modified", "unchanged"}
