"""Comment threads on plan elements, kept in the issue's comments.json."""

import fcntl  # POSIX only: plan-review runs on macOS and Linux
import os
import stat
import tempfile
import uuid
from collections.abc import Callable, Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, TypeAdapter, field_validator

Author = Literal["owner", "claude"]

# Anchors that are always on the page, whatever the plan holds.
FIXED_ANCHOR_PREFIXES = ("tab:", "header:")


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
        return self._update(
            thread_id, lambda t: t.messages.append(Message(author=author, text=text))
        )

    def set_resolved(self, thread_id: str, resolved: bool) -> Thread:
        return self._update(thread_id, lambda t: setattr(t, "resolved", resolved))

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


@contextmanager
def file_lock(path: Path) -> Generator[None]:
    """Hold an exclusive lock for a read-modify-write of `path`.

    The server's request threads and the CLI (another process) write the same files, so
    the lock is the OS's (flock on a sibling `.lock` file), not just a threading.Lock.
    """
    with path.with_name(f"{path.name}.lock").open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _umask() -> int:
    mask = os.umask(0)  # reading it means setting it: put it straight back
    os.umask(mask)
    return mask


# Read once, at import: os.umask is process-wide, so not safe to call while threads write.
_NEW_FILE_MODE = 0o666 & ~_umask()


def write_atomically(path: Path, data: bytes) -> None:
    # Write a sibling file then rename: a reader never sees a half-written file. The
    # sibling's name is unique, so two writers never share (and break) one.
    try:
        mode = stat.S_IMODE(path.stat().st_mode)  # keep the file's permissions
    except FileNotFoundError:
        mode = _NEW_FILE_MODE  # as open() would create it (temp files are private)
    # Opened outside `with` so the cleanup below also covers a failed os.replace.
    tmp = tempfile.NamedTemporaryFile(  # noqa: SIM115 - closed by `with tmp` below
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
    )
    try:
        with tmp:
            tmp.write(data)
            tmp.flush()
            os.fchmod(tmp.fileno(), mode)
        os.replace(tmp.name, path)
    except BaseException:
        Path(tmp.name).unlink(missing_ok=True)  # leave no stray temporary file behind
        raise


def require_text(text: str) -> None:
    # Checked up front so callers get BlankComment, not a wrapped pydantic error.
    if not text.strip():
        raise BlankComment
