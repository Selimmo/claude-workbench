"""What the owner may do, and when.

Plain functions that read a GrillState and raise GrillError. Each refusal is written once here;
the store and the routes call these and add no rule of their own.
"""

from plan_review.grill.drafts import AnswerDraft
from plan_review.grill.state import GrillError, GrillState, Question, SubmittedAnswer


def require_open(state: GrillState) -> None:
    """After a confirm nobody may change the grill."""
    if state.confirmed_at is not None:
        raise GrillError(["the owner already confirmed the grill"], conflict=True)


def require_owners_turn(state: GrillState) -> None:
    require_open(state)
    if not state.owners_turn():
        raise GrillError(["waiting for the agent to handle your last action"], conflict=True)


def require_can_submit(state: GrillState, answers: list[SubmittedAnswer]) -> None:
    require_owners_turn(state)
    if state.done:
        raise GrillError(["the grill is done: confirm it or say 'not yet'"], conflict=True)
    problems = _answer_problems(state, answers)
    if problems:
        raise GrillError(problems)


def require_can_confirm(state: GrillState) -> None:
    require_owners_turn(state)
    if not state.done:
        raise GrillError(["The agent has not said the grill is done yet"], conflict=True)


def require_can_reopen(state: GrillState, text: str) -> None:
    require_can_confirm(state)
    if not text.strip():
        raise GrillError(["text: say what is missing"])


def require_draftable(state: GrillState, question_id: str) -> None:
    """A draft needs a question that exists and is still open (both are a 404)."""
    if state.question(question_id).answer is not None:
        raise GrillError([f"question '{question_id}' is already answered"], missing=True)


def answers_to_submit(state: GrillState, drafts: dict[str, AnswerDraft]) -> list[SubmittedAnswer]:
    """The drafts of the questions still open, in draft order.

    A draft for a question the agent closed meanwhile is left out rather than refusing the
    whole submit."""
    open_ids = {q.id for q in state.open_questions()}
    return [
        SubmittedAnswer(question_id=qid, **draft.model_dump())
        for qid, draft in drafts.items()
        if qid in open_ids
    ]


def _answer_problems(state: GrillState, answers: list[SubmittedAnswer]) -> list[str]:
    """One line per way the owner's answers are not exactly one valid response per open question."""
    open_by_id = {q.id: q for q in state.open_questions()}
    problems: list[str] = []
    seen: set[str] = set()
    for i, given in enumerate(answers):
        problem = _placement_problem(given, open_by_id, seen) or _response_problem(
            given, open_by_id[given.question_id]
        )
        if problem:
            problems.append(f"answers.{i}.{problem}")
        seen.add(given.question_id)
    problems.extend(f"{qid}: needs a response" for qid in open_by_id if qid not in seen)
    return problems


def _placement_problem(
    given: SubmittedAnswer, open_by_id: dict[str, Question], seen: set[str]
) -> str | None:
    if given.question_id not in open_by_id:
        return f"question_id: no open question '{given.question_id}'"
    if given.question_id in seen:
        return f"question_id: '{given.question_id}' is answered twice"
    return None


def _response_problem(given: SubmittedAnswer, question: Question) -> str | None:
    if given.kind in ("own", "ask"):
        return f"kind: '{given.kind}' is no longer accepted; pick a choice or Other"
    if given.kind == "choice":
        if given.choice_id is None:
            return "choice_id: needed to pick a choice"
        if given.choice_id not in {c.id for c in question.choices}:
            return f"choice_id: '{given.choice_id}' is not a choice of '{question.id}'"
        return None
    if not (given.text or "").strip():
        return "text: needed for Other"
    return None
