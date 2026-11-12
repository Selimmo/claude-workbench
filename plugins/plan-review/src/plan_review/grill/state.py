"""What a grill holds: rounds of questions the owner answers on a page of their own.

The data only. It imports nothing else from grill/, so the agent's turn, the owner's rules and
the store can all import it. The state lives in the run's grill.json (see store.py).
"""

from datetime import UTC, datetime
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from plan_review.review.threads import Message

MAX_REPLIES: Final = 3  # the agent's replies to Others on one question; then it must settle


class GrillError(Exception):
    """A grill file or request that cannot be accepted, one readable line per problem."""

    def __init__(self, errors: list[str], *, missing: bool = False, conflict: bool = False) -> None:
        super().__init__("\n".join(errors))
        self.errors = errors
        self.missing = missing
        self.conflict = conflict  # wrong turn or state (the server answers 409), else 422


def _now() -> datetime:
    return datetime.now(UTC)


class Choice(BaseModel):
    model_config = ConfigDict(extra="forbid")  # a typo in a turn must not be dropped

    id: str
    label: str
    description: str


class Answer(BaseModel):
    kind: Literal["choice", "own", "other"]  # "own" only in 0.1.9 files
    choice_id: str | None = None
    text: str | None = None  # a note on the choice, or the Other (or old own) text


class Question(BaseModel):
    id: str
    title: str
    explanation: str
    choices: list[Choice]  # the first is the recommendation
    updated: bool = False  # explanation or choices revised in a reply
    thread: list[Message] = []  # the owner's Other answers and the agent's replies
    answer: Answer | None = None  # None while open

    def replies(self) -> int:
        """The agent's messages in the thread, old ones included."""
        return sum(1 for m in self.thread if m.author != "owner")

    def must_settle(self) -> bool:
        return self.replies() >= MAX_REPLIES

    def awaiting_reply(self) -> bool:
        """Open, and the thread ends with the owner's Other."""
        return self.answer is None and bool(self.thread) and self.thread[-1].author == "owner"


class Round(BaseModel):
    n: int
    questions: list[Question]


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    topic: str
    decision: str
    choice: str
    why: str | None = None
    question_id: str | None = None  # the question it came from, shown on the page
    replaces: str | None = None  # id of an earlier decision, then shown struck through


class SubmittedAnswer(BaseModel):
    question_id: str
    kind: Literal["choice", "other", "own", "ask"]
    choice_id: str | None = None
    text: str | None = None


class OwnerAction(BaseModel):
    kind: Literal["answers", "reopen", "confirm"]
    answers: list[SubmittedAnswer] = []
    text: str | None = None  # the owner's 'not yet' comment, for 'reopen'
    at: datetime = Field(default_factory=_now)


class GrillState(BaseModel):
    title: str
    rounds: list[Round] = []
    decisions: list[Decision] = []
    out_of_scope: list[str] = []
    done: bool = False  # the agent marked the frontier empty
    confirmed_at: datetime | None = None
    log: list[OwnerAction] = []  # append-only: every submit, reopen and confirm
    handled: int = 0  # owner actions the agent has answered (set by each post)

    def owners_turn(self) -> bool:
        """Whether the agent has handled everything the owner did."""
        return self.handled == len(self.log)

    def questions_by_id(self) -> dict[str, Question]:
        """Every question of every round, answered or open, in round order."""
        return {q.id: q for r in self.rounds for q in r.questions}

    def question(self, question_id: str) -> Question:
        found = self.questions_by_id().get(question_id)
        if found is None:
            raise GrillError([f"no question '{question_id}'"], missing=True)
        return found

    def open_questions(self) -> list[Question]:
        return [q for r in self.rounds for q in r.questions if q.answer is None]
