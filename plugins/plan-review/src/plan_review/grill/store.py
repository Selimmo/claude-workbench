"""How a grill is saved and locked.

The state lives in the run's grill.json. It has two writers in two processes: the agent
(`plan-review grill post`) and the viewer server (the owner's submit, confirm and reopen).
Every read-modify-write therefore holds the file lock and writes the file whole.
"""

from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from plan_review.grill.drafts import GrillDraftStore
from plan_review.grill.owner_rules import (
    require_can_confirm,
    require_can_reopen,
    require_can_submit,
    require_open,
)
from plan_review.grill.pending_text import pending_actions
from plan_review.grill.state import (
    Answer,
    GrillError,
    GrillState,
    OwnerAction,
    SubmittedAnswer,
)
from plan_review.grill.turn import Turn
from plan_review.review.threads import Message
from plan_review.utils.json_files import BrokenFile, named_errors
from plan_review.utils.safe_files import file_lock, write_atomically


def drafts_then_grill(drafts: GrillDraftStore) -> AbstractContextManager[None]:
    """Hold the drafts lock; the lock order for anything that touches both files.

    The drafts lock comes first, then grill.json (each GrillStore method takes its own lock
    inside), so a draft edit cannot land between a submit's reads and its writes."""
    return drafts.held()


class GrillStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def get(self) -> GrillState:
        return load_grill(self._path)

    def post(self, turn: Turn) -> GrillState:
        """Apply the agent's turn; the first one creates grill.json."""
        with file_lock(self._path):
            current = self.get() if self._path.is_file() else None
            if current is not None:
                require_open(current)
            state = turn.apply(current)
            state.handled = len(state.log)
            self._save(state)
        return state

    def submit(self, answers: list[SubmittedAnswer]) -> OwnerAction:
        """Record the owner's response to every open question, all at once."""
        with file_lock(self._path):
            state = self.get()
            require_can_submit(state, answers)
            questions = state.questions_by_id()
            for given in answers:
                question = questions[given.question_id]
                if given.kind == "other":
                    question.thread.append(Message(author="owner", text=given.text or ""))
                    continue
                question.answer = Answer(
                    kind="choice",
                    choice_id=given.choice_id,
                    text=given.text,
                )
            action = OwnerAction(kind="answers", answers=answers)
            state.log.append(action)
            self._save(state)
        return action

    def confirm(self) -> OwnerAction:
        """The owner accepts the shared understanding; only once the agent says it is done."""
        with file_lock(self._path):
            state = self.get()
            require_can_confirm(state)
            action = OwnerAction(kind="confirm")
            state.log.append(action)
            state.confirmed_at = action.at
            self._save(state)
        return action

    def reopen(self, text: str) -> OwnerAction:
        """The owner says 'not yet' and what is missing; grilling goes on."""
        with file_lock(self._path):
            state = self.get()
            require_can_reopen(state, text)
            action = OwnerAction(kind="reopen", text=text)
            state.log.append(action)
            state.done = False
            self._save(state)
        return action

    def pending(self) -> list[dict[str, Any]]:
        return pending_actions(self.get())

    def _save(self, state: GrillState) -> None:
        write_atomically(self._path, state.model_dump_json(indent=2).encode())


@dataclass(frozen=True)
class PostedTurn:
    state: GrillState
    drafts_problem: str | None  # the unreadable drafts file, by name; the turn is posted anyway


def post_turn(store: GrillStore, drafts: GrillDraftStore, turn_json: bytes) -> PostedTurn:
    """Post the agent's turn, then drop the drafts of the questions it closed.

    The turn is parsed inside the lock, so a bad turn waits for a running submit like a good
    one. GrillError (a bad turn too) propagates."""
    with drafts_then_grill(drafts):
        state = store.post(Turn.parse(turn_json))
        try:
            drafts.keep_only({q.id for q in state.open_questions()})
        except BrokenFile as error:
            return PostedTurn(state, str(error))
    return PostedTurn(state, None)


def load_grill(path: Path) -> GrillState:
    if not path.is_file():
        raise GrillError([f"{path.as_posix()}: file not found"], missing=True)
    try:
        return GrillState.model_validate_json(path.read_bytes())
    except ValidationError as error:
        raise GrillError(named_errors(path, error)) from error
