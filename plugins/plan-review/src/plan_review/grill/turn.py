"""The agent's side of the grill: one turn of replies, decisions and the next round."""

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from plan_review.grill.grill import (
    MAX_REPLIES,
    Answer,
    Choice,
    Decision,
    GrillError,
    GrillState,
    Question,
    Round,
)
from plan_review.review.threads import Message
from plan_review.utils.json_files import readable_errors


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _two_distinct_choices(choices: list[Choice]) -> list[Choice]:
    if len(choices) < 2:
        raise ValueError("needs at least two choices")
    if len({c.id for c in choices}) != len(choices):
        raise ValueError("choice ids must be unique")
    return choices


class Revision(_Strict):
    explanation: str
    choices: list[Choice]  # the first is the recommendation

    _checked = field_validator("choices")(_two_distinct_choices)


class NewQuestion(Revision):
    id: str
    title: str


class Reply(_Strict):
    question_id: str  # must be awaiting a reply and not yet at the limit
    text: str
    revised: Revision | None = None  # replaces the question's explanation and choices


class Turn(_Strict):
    title: str | None = None  # required on the first turn only
    replies: list[Reply] = []
    decisions: list[Decision] = []
    out_of_scope: list[str] = []
    round: list[NewQuestion] | None = None  # the next round
    done: bool = False  # the frontier is empty: the page offers Confirm

    @classmethod
    def parse(cls, raw: str | bytes) -> Turn:
        """A turn from JSON text; GrillError with one line per problem."""
        try:
            return cls.model_validate_json(raw)
        except ValidationError as error:
            raise GrillError(readable_errors(error)) from error

    def apply(self, state: GrillState | None) -> GrillState:
        """The state after this turn; GrillError with every problem found."""
        errors: list[str] = []
        if state is None:
            if self.title is None:
                errors.append("title: required on the first turn")
            state = GrillState(title=self.title or "")
        questions = {q.id: q for r in state.rounds for q in r.questions}
        settling = self._settled(questions)
        errors.extend(self._response_problems(questions, settling))
        used = set(questions)
        for i, new in enumerate(self.round or []):
            if new.id in used:
                errors.append(f"round.{i}.id: '{new.id}' is already used by a question")
            used.add(new.id)
        errors.extend(self._decision_problems(state, used))
        errors.extend(self._frontier_problems(state, questions, settling))
        if errors:
            raise GrillError(errors)
        by_id = {q.id: q for r in state.rounds for q in r.questions}
        for reply in self.replies:
            question = by_id[reply.question_id]
            question.thread.append(Message(author="agent", text=reply.text))
            if reply.revised is not None:
                question.explanation = reply.revised.explanation
                question.choices = reply.revised.choices
                question.updated = True
        for question_id in settling:
            owner_text = next(
                m.text for m in reversed(by_id[question_id].thread) if m.author == "owner"
            )
            by_id[question_id].answer = Answer(kind="other", text=owner_text)
        state.decisions.extend(self.decisions)
        state.out_of_scope.extend(self.out_of_scope)
        state.done = self.done or (state.done and not self.round)
        if self.round:
            new = [Question(**q.model_dump()) for q in self.round]
            state.rounds.append(Round(n=len(state.rounds) + 1, questions=new))
        return state

    def _settled(self, questions: dict[str, Question]) -> set[str]:
        """Questions awaiting a reply that a decision of this turn settles."""
        return {
            d.question_id
            for d in self.decisions
            if d.question_id is not None
            and d.question_id in questions
            and questions[d.question_id].awaiting_reply()
        }

    def _response_problems(self, questions: dict[str, Question], settling: set[str]) -> list[str]:
        """Every question awaiting a reply gets one reply or one settling decision, not both."""
        errors: list[str] = []
        replied: set[str] = set()
        for i, reply in enumerate(self.replies):
            where = f"replies.{i}.question_id"
            asked = questions.get(reply.question_id)
            if asked is None or not asked.awaiting_reply() or reply.question_id in replied:
                errors.append(f"{where}: '{reply.question_id}' is not awaiting a reply")
            elif asked.must_settle():
                errors.append(
                    f"{where}: question '{asked.id}' has had {MAX_REPLIES} replies; "
                    "it must be settled with a decision"
                )
            replied.add(reply.question_id)
        for q in questions.values():
            if not q.awaiting_reply():
                continue
            if q.id in replied and q.id in settling:
                errors.append(
                    f"replies: question '{q.id}' is replied to and settled in one turn; "
                    "do one of them"
                )
            elif q.id not in replied and q.id not in settling:
                errors.append(f"replies: question '{q.id}' is awaiting a reply or a decision")
        return errors

    def _decision_problems(self, state: GrillState, question_ids: set[str]) -> list[str]:
        errors: list[str] = []
        known = {d.id for d in state.decisions}
        replaced = {d.replaces for d in state.decisions if d.replaces}
        for i, decided in enumerate(self.decisions):
            where = f"decisions.{i}"
            if decided.id in known:
                errors.append(f"{where}.id: '{decided.id}' is already used by a decision")
            if decided.replaces is not None:
                if decided.replaces not in known:
                    errors.append(f"{where}.replaces: no decision '{decided.replaces}'")
                elif decided.replaces in replaced:
                    errors.append(f"{where}.replaces: '{decided.replaces}' is already replaced")
                replaced.add(decided.replaces)
            if decided.question_id is not None and decided.question_id not in question_ids:
                errors.append(f"{where}.question_id: no question '{decided.question_id}'")
            known.add(decided.id)
        return errors

    def _frontier_problems(
        self, state: GrillState, questions: dict[str, Question], settling: set[str]
    ) -> list[str]:
        """`done` needs no open question, and every other turn must leave the owner something."""
        still_open = [q.id for q in questions.values() if q.answer is None and q.id not in settling]
        still_open.extend(q.id for q in self.round or [])
        if self.done and still_open:
            return [f"done: questions are still open: {', '.join(still_open)}"]
        if not (still_open or self.done or state.done):
            return [
                "round: nothing is left for the owner; post a round, answer an Other or set done"
            ]
        return []
