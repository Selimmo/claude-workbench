"""Comment threads on plan elements, kept in the issue's comments.json."""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, TypeAdapter, field_validator

from plan_review.settings.migration import LegacyAuthor
from plan_review.utils.json_files import read_file
from plan_review.utils.safe_files import file_lock, write_atomically
from plan_review.utils.text import BlankComment, require_text

Author = Literal["owner", "agent", LegacyAuthor]

# Anchors that are always on the page, whatever the plan holds.
FIXED_ANCHOR_PREFIXES = ("tab:", "header:")


class ThreadNotFound(KeyError):
    pass


class ResolveRefused(Exception):
    """The owner spoke last: the agent has not answered yet, so there is nothing to resolve."""

    def __init__(self, thread_id: str) -> None:
        super().__init__(f"thread '{thread_id}' awaits an answer from the agent")
        self.thread_id = thread_id


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

    @property
    def awaiting_answer(self) -> bool:
        """The owner has the last word, so the agent still owes an answer."""
        return self.messages[-1].author == "owner"


_Threads = TypeAdapter(list[Thread])


class ThreadStore:
    """Reads the file on every call and writes it whole, so the server and the CLI
    (separate processes) always see each other's latest writes."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def all(self) -> list[Thread]:
        return read_file(self._path, _Threads) or []

    def get(self, thread_id: str) -> Thread:
        thread = next((t for t in self.all() if t.id == thread_id), None)
        if thread is None:
            raise ThreadNotFound(thread_id)
        return thread

    def orphaned(self, element_ids: set[str]) -> list[Thread]:
        """Threads whose element left the plan. Threads on a whole tab (`tab:...`) or on
        the plan's header (`header:title`, `header:summary`) never orphan."""
        return [
            t
            for t in self.all()
            if not t.anchor.startswith(FIXED_ANCHOR_PREFIXES) and t.anchor not in element_ids
        ]

    def create(self, anchor: str, text: str) -> Thread:
        require_text(text)
        thread = Thread(
            id=f"t-{uuid.uuid4().hex[:8]}",
            anchor=anchor,
            messages=[Message(author="owner", text=text)],
        )
        with file_lock(self._path):
            self._save([*self.all(), thread])
        return thread

    def reply(self, thread_id: str, text: str, *, author: Author) -> Thread:
        require_text(text)

        def add(thread: Thread) -> None:
            thread.messages.append(Message(author=author, text=text))
            if author == "owner":
                thread.resolved = False  # a follow-up reopens the thread

        return self._update(thread_id, add)

    def set_resolved(self, thread_id: str, resolved: bool) -> Thread:
        def change(thread: Thread) -> None:
            if resolved and thread.awaiting_answer:
                raise ResolveRefused(thread.id)
            thread.resolved = resolved

        return self._update(thread_id, change)

    def _update(self, thread_id: str, change: Callable[[Thread], object]) -> Thread:
        with file_lock(self._path):
            threads = self.all()
            thread = next((t for t in threads if t.id == thread_id), None)
            if thread is None:
                raise ThreadNotFound(thread_id)
            change(thread)
            self._save(threads)
        return thread

    def _save(self, threads: list[Thread]) -> None:
        write_atomically(self._path, _Threads.dump_json(threads, indent=2))
