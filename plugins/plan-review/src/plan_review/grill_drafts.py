"""The owner's unsent answers on the grill page, kept in the run's grill_drafts.json.

Like review drafts, they live in their own file: Claude and the grill state only ever see
submitted answers. Kept on disk because `serve` picks a new port, so browser storage is
empty on every run. The server owns this file; the agent never reads it.
"""

import threading
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, TypeAdapter, model_validator

from plan_review.threads import file_lock, write_atomically


class AnswerDraft(BaseModel):
    """A SubmittedAnswer without its question id (the file is keyed by it)."""

    kind: Literal["choice", "own", "ask"]
    choice_id: str | None = None
    text: str | None = None  # for 'choice': an optional note

    @model_validator(mode="after")
    def _has_what_its_kind_needs(self) -> Self:
        if self.kind == "choice" and self.choice_id is None:
            raise ValueError("a choice needs choice_id")
        if self.kind != "choice" and not (self.text or "").strip():
            raise ValueError(f"an {'own answer' if self.kind == 'own' else 'ask back'} needs text")
        return self


_Drafts = TypeAdapter(dict[str, AnswerDraft])


class GrillDraftStore:
    """Read on every call and written whole, like DraftStore."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._holding = threading.local()

    @contextmanager
    def held(self) -> Generator[None]:
        """Keep the drafts locked across a whole submit."""
        with file_lock(self._path):
            self._holding.on = True
            try:
                yield
            finally:
                self._holding.on = False

    @contextmanager
    def _lock(self) -> Generator[None]:
        if getattr(self._holding, "on", False):
            yield
        else:
            with file_lock(self._path):
                yield

    def all(self) -> dict[str, AnswerDraft]:
        if not self._path.is_file():
            return {}
        return _Drafts.validate_json(self._path.read_bytes())

    def put(self, question_id: str, draft: AnswerDraft) -> AnswerDraft:
        with self._lock():
            self._save({**self.all(), question_id: draft})
        return draft

    def discard(self, question_id: str) -> None:
        self.clear({question_id})

    def clear(self, question_ids: set[str]) -> None:
        """Remove these drafts (e.g. just submitted), keeping any made meanwhile."""
        with self._lock():
            self._save({k: d for k, d in self.all().items() if k not in question_ids})

    def _save(self, drafts: dict[str, AnswerDraft]) -> None:
        write_atomically(self._path, _Drafts.dump_json(drafts, indent=2))
