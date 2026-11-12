"""What the agent is told is waiting (`plan-review grill pending`)."""

from typing import Any

from plan_review.grill.state import GrillState, OwnerAction, Question


def pending_actions(state: GrillState) -> list[dict[str, Any]]:
    """What the owner did that the agent has not answered yet, in words the agent can use."""
    questions = state.questions_by_id()
    return [_describe(action, questions) for action in state.log[state.handled :]]


def _describe(action: OwnerAction, questions: dict[str, Question]) -> dict[str, Any]:
    if action.kind != "answers":
        return action.model_dump(mode="json", include={"kind", "text", "at"}, exclude_none=True)
    described: list[dict[str, Any]] = []
    for given in action.answers:
        question = questions[given.question_id]
        item: dict[str, Any] = {
            "question_id": given.question_id,
            "question": question.title,
            "kind": given.kind,
        }
        if given.choice_id is not None:
            item["choice_id"] = given.choice_id
            item["choice"] = next(c.label for c in question.choices if c.id == given.choice_id)
        if given.text:
            item["text"] = given.text
        if given.kind == "other" and question.must_settle():
            item["must_settle"] = True
        described.append(item)
    return {"kind": "answers", "answers": described}
