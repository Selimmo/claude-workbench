"""The owner's unsent review comments, kept in the issue's drafts.json.

Drafts live in their own file, not in comments.json: Claude, the CLI and the approval
check only ever see submitted comments. Kept on disk rather than in the browser because
`serve` picks a new port (so a new origin, with empty browser storage) on every run.
"""

import threading
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field, TypeAdapter

from plan_review.threads import file_lock, require_text, write_atomically


class DraftNotFound(KeyError):
    pass


class Draft(BaseModel):
    id: str
    anchor: str
    text: str
    # Set for a reply in an existing thread; None for a new comment on `anchor`.
    thread_id: str | None = None
    at: datetime = Field(default_factory=lambda: datetime.now(UTC))


_Drafts = TypeAdapter(list[Draft])


class DraftStore:
    """Same file discipline as ThreadStore: read on every call, write whole."""

    def __init__(self, path: Path) -> None:
        self._path = path
        # Per thread: one request may hold the file lock across several calls (see held()).
        self._holding = threading.local()

    @contextmanager
    def held(self) -> Generator[None]:
        """Keep the drafts locked across several calls, e.g. a whole submit, so no other
        request (or tab) changes a draft between reading it and removing it."""
        with file_lock(self._path):
            self._holding.on = True
            try:
                yield
            finally:
                self._holding.on = False

    @contextmanager
    def _lock(self) -> Generator[None]:
        # flock can't be taken twice from one thread on new handles: reuse a held lock.
        if getattr(self._holding, "on", False):
            yield
        else:
            with file_lock(self._path):
                yield

    def all(self) -> list[Draft]:
        if not self._path.is_file():
            return []
        return _Drafts.validate_json(self._path.read_bytes())

    def add(self, anchor: str, text: str, *, thread_id: str | None = None) -> Draft:
        require_text(text)
        draft = Draft(id=f"d-{uuid.uuid4().hex[:8]}", anchor=anchor, text=text, thread_id=thread_id)
        with self._lock():
            self._save([*self.all(), draft])
        return draft

    def edit(self, draft_id: str, text: str) -> Draft:
        require_text(text)
        with self._lock():
            drafts = self.all()
            draft = _find(drafts, draft_id)
            draft.text = text
            self._save(drafts)
        return draft

    def discard(self, draft_id: str) -> None:
        with self._lock():
            drafts = self.all()
            _find(drafts, draft_id)
            self._save([d for d in drafts if d.id != draft_id])

    def discard_all(self, draft_ids: set[str]) -> None:
        """Remove these drafts (e.g. just submitted), keeping any added meanwhile."""
        with self._lock():
            self._save([d for d in self.all() if d.id not in draft_ids])

    def _save(self, drafts: list[Draft]) -> None:
        write_atomically(self._path, _Drafts.dump_json(drafts, indent=2))


def _find(drafts: list[Draft], draft_id: str) -> Draft:
    draft = next((d for d in drafts if d.id == draft_id), None)
    if draft is None:
        raise DraftNotFound(draft_id)
    return draft
