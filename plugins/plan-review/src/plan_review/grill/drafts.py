"""The owner's unsent answers on the grill page, kept in the run's grill_drafts.json.

Like review drafts, they live in their own file: The agent and the grill state only ever see
submitted answers. Kept on disk because `serve` picks a new port, so browser storage is
empty on every run. The server owns this file; the agent never reads it.
"""

from contextlib import AbstractContextManager
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, TypeAdapter, model_validator

from plan_review.utils.json_files import read_file
from plan_review.utils.safe_files import HeldLock, write_atomically


class AnswerDraft(BaseModel):
    """A SubmittedAnswer without its question id (the file is keyed by it)."""

    kind: Literal["choice", "other"]
    choice_id: str | None = None
    text: str | None = None  # a choice's optional note; Other's text (may be empty while typing)

    @model_validator(mode="after")
    def _has_what_its_kind_needs(self) -> Self:
        if self.kind == "choice" and self.choice_id is None:
            raise ValueError("a choice needs choice_id")
        return self


_Drafts = TypeAdapter(dict[str, AnswerDraft])


class GrillDraftStore:
    """Read on every call and written whole, like DraftStore."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._locking = HeldLock(path)

    def held(self) -> AbstractContextManager[None]:
        """Keep the drafts locked across several calls, e.g. a whole submit, so no other
        request (or tab) changes a draft between reading it and removing it."""
        return self._locking.held()

    def all(self) -> dict[str, AnswerDraft]:
        return read_file(self._path, _Drafts) or {}

    def put(self, question_id: str, draft: AnswerDraft) -> AnswerDraft:
        with self._locking.lock():
            self._save({**self.all(), question_id: draft})
        return draft

    def discard(self, question_id: str) -> None:
        self.clear({question_id})

    def clear(self, question_ids: set[str]) -> None:
        """Remove these drafts (e.g. just submitted), keeping any made meanwhile."""
        with self._locking.lock():
            self._save({k: d for k, d in self.all().items() if k not in question_ids})

    def keep_only(self, question_ids: set[str]) -> None:
        """Drop the drafts of every question not in this set (e.g. closed by the agent's turn)."""
        with self._locking.lock():
            kept = {k: d for k, d in self.all().items() if k in question_ids}
            if kept != self.all():
                self._save(kept)

    def _save(self, drafts: dict[str, AnswerDraft]) -> None:
        write_atomically(self._path, _Drafts.dump_json(drafts, indent=2))
