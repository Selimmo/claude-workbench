"""Comment threads on plan elements, kept in the issue's comments.json."""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, TypeAdapter, field_validator

Author = Literal["owner", "claude"]


class ThreadNotFound(KeyError):
    pass


class BlankComment(ValueError):
    def __init__(self) -> None:
        super().__init__("comment text is empty")


class Message(BaseModel):
    author: Author
    text: str
    at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("text")
    @classmethod
    def _not_blank(cls, text: str) -> str:
        if not text.strip():
            raise BlankComment
        return text


class Thread(BaseModel):
    id: str
    anchor: str
    messages: list[Message]
    resolved: bool = False


_Threads = TypeAdapter(list[Thread])


class ThreadStore:
    """Reads the file on every call and writes it whole, so the server and the CLI
    (separate processes) always see each other's latest writes."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def all(self) -> list[Thread]:
        if not self._path.is_file():
            return []
        return _Threads.validate_json(self._path.read_bytes())

    def orphaned(self, element_ids: set[str]) -> list[Thread]:
        """Threads whose element left the plan. Tab-wide threads (`tab:...`) never orphan."""
        return [
            t for t in self.all() if not t.anchor.startswith("tab:") and t.anchor not in element_ids
        ]

    def create(self, anchor: str, text: str) -> Thread:
        _require_text(text)
        thread = Thread(
            id=f"t-{uuid.uuid4().hex[:8]}",
            anchor=anchor,
            messages=[Message(author="owner", text=text)],
        )
        self._save([*self.all(), thread])
        return thread

    def reply(self, thread_id: str, text: str, *, author: Author) -> Thread:
        _require_text(text)
        return self._update(
            thread_id, lambda t: t.messages.append(Message(author=author, text=text))
        )

    def set_resolved(self, thread_id: str, resolved: bool) -> Thread:
        return self._update(thread_id, lambda t: setattr(t, "resolved", resolved))

    def _update(self, thread_id: str, change: Callable[[Thread], object]) -> Thread:
        threads = self.all()
        thread = next((t for t in threads if t.id == thread_id), None)
        if thread is None:
            raise ThreadNotFound(thread_id)
        change(thread)
        self._save(threads)
        return thread

    def _save(self, threads: list[Thread]) -> None:
        # Write a sibling file then rename: a reader never sees a half-written file.
        tmp = self._path.with_suffix(".tmp")
        tmp.write_bytes(_Threads.dump_json(threads, indent=2))
        tmp.replace(self._path)


def _require_text(text: str) -> None:
    # Checked up front so callers get BlankComment, not a wrapped pydantic error.
    if not text.strip():
        raise BlankComment
