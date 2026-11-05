"""The grill: rounds of questions the owner answers on a page of their own.

The state lives in the run's grill.json. It has two writers in two processes: the agent
(`plan-review grill post`) and the viewer server (the owner's submit, confirm and reopen).
Every read-modify-write therefore holds the file lock and writes the file whole.
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from plan_review.plan import readable_errors
from plan_review.threads import Message, file_lock, write_atomically

if TYPE_CHECKING:
    from plan_review.grill_turn import Turn

MAX_ASKS: Final = 3  # asks back per question; not a pipeline.json setting


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
    kind: Literal["choice", "own"]
    choice_id: str | None = None
    text: str | None = None  # the own answer, or a note on the picked choice


class Question(BaseModel):
    id: str
    title: str
    explanation: str
    choices: list[Choice]  # the first is the recommendation
    updated: bool = False  # explanation or choices revised after an ask back
    thread: list[Message] = []  # asks back (owner) and replies (claude)
    answer: Answer | None = None  # None while open

    def asks(self) -> int:
        return sum(1 for m in self.thread if m.author == "owner")

    def awaiting_reply(self) -> bool:
        """Open, and the owner asked back and Claude has not replied yet."""
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
    kind: Literal["choice", "own", "ask"]
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
        """Whether Claude has handled everything the owner did."""
        return self.handled == len(self.log)

    def question(self, question_id: str) -> Question:
        for r in self.rounds:
            for q in r.questions:
                if q.id == question_id:
                    return q
        raise GrillError([f"no question '{question_id}'"], missing=True)

    def open_questions(self) -> list[Question]:
        return [q for r in self.rounds for q in r.questions if q.answer is None]


class GrillStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def get(self) -> GrillState:
        return load_grill(self._path)

    def post(self, turn: Turn) -> GrillState:
        """Apply the agent's turn; the first one creates grill.json."""
        with file_lock(self._path):
            current = self.get() if self._path.is_file() else None
            if current is not None and current.confirmed_at is not None:
                raise GrillError(["the owner already confirmed the grill"], conflict=True)
            state = turn.apply(current)
            state.handled = len(state.log)
            self._save(state)
        return state

    def submit(self, answers: list[SubmittedAnswer]) -> OwnerAction:
        """Record the owner's response to every open question, all at once."""
        with file_lock(self._path):
            state = self.get()
            _require_owners_turn(state)
            if state.done:
                raise GrillError(["the grill is done: confirm it or say 'not yet'"], conflict=True)
            problems = _answer_problems(state, answers)
            if problems:
                raise GrillError(problems)
            for given in answers:
                question = next(q for q in state.open_questions() if q.id == given.question_id)
                if given.kind == "ask":
                    question.thread.append(Message(author="owner", text=given.text or ""))
                    continue
                question.answer = Answer(
                    kind="choice" if given.kind == "choice" else "own",
                    choice_id=given.choice_id,
                    text=given.text,
                )
            action = OwnerAction(kind="answers", answers=answers)
            state.log.append(action)
            self._save(state)
        return action

    def confirm(self) -> OwnerAction:
        """The owner accepts the shared understanding; only once Claude says it is done."""
        with file_lock(self._path):
            state = self.get()
            _require_owners_turn(state)
            if not state.done:
                raise GrillError(["Claude has not said the grill is done yet"], conflict=True)
            action = OwnerAction(kind="confirm")
            state.log.append(action)
            state.confirmed_at = action.at
            self._save(state)
        return action

    def reopen(self, text: str) -> OwnerAction:
        """The owner says 'not yet' and what is missing; grilling goes on."""
        with file_lock(self._path):
            state = self.get()
            _require_owners_turn(state)
            if not state.done:
                raise GrillError(["Claude has not said the grill is done yet"], conflict=True)
            if not text.strip():
                raise GrillError(["text: say what is missing"])
            action = OwnerAction(kind="reopen", text=text)
            state.log.append(action)
            state.done = False
            self._save(state)
        return action

    def pending(self) -> list[dict[str, Any]]:
        """What the owner did that the agent has not answered yet, in words the agent can use."""
        state = self.get()
        titles = {q.id: q for r in state.rounds for q in r.questions}
        return [_describe(action, titles) for action in state.log[state.handled :]]

    def _save(self, state: GrillState) -> None:
        write_atomically(self._path, state.model_dump_json(indent=2).encode())


def _require_owners_turn(state: GrillState) -> None:
    if state.confirmed_at is not None:
        raise GrillError(["the owner already confirmed the grill"], conflict=True)
    if not state.owners_turn():
        raise GrillError(["waiting for Claude to handle your last action"], conflict=True)


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
        described.append(item)
    return {"kind": "answers", "answers": described}


def _answer_problems(state: GrillState, answers: list[SubmittedAnswer]) -> list[str]:
    """One line per way the owner's answers are not exactly one valid response per open question."""
    open_by_id = {q.id: q for q in state.open_questions()}
    problems: list[str] = []
    seen: set[str] = set()
    for i, given in enumerate(answers):
        where = f"answers.{i}"
        question = open_by_id.get(given.question_id)
        if question is None:
            problems.append(f"{where}.question_id: no open question '{given.question_id}'")
            continue
        if given.question_id in seen:
            problems.append(f"{where}.question_id: '{given.question_id}' is answered twice")
            continue
        seen.add(given.question_id)
        if given.kind == "choice":
            if given.choice_id is None:
                problems.append(f"{where}.choice_id: needed to pick a choice")
            elif given.choice_id not in {c.id for c in question.choices}:
                problems.append(
                    f"{where}.choice_id: '{given.choice_id}' is not a choice of '{question.id}'"
                )
        elif not (given.text or "").strip():
            what = "an own answer" if given.kind == "own" else "an ask back"
            problems.append(f"{where}.text: needed for {what}")
        elif given.kind == "ask" and question.asks() >= MAX_ASKS:
            problems.append(
                f"{where}: question '{question.id}' has used its {MAX_ASKS} asks back; "
                "pick a choice or write your own answer"
            )
    problems.extend(f"{qid}: needs a response" for qid in open_by_id if qid not in seen)
    return problems


def load_grill(path: Path) -> GrillState:
    if not path.is_file():
        raise GrillError([f"{path.as_posix()}: file not found"], missing=True)
    try:
        return GrillState.model_validate_json(path.read_bytes())
    except ValidationError as error:
        raise GrillError(readable_errors(error)) from error
