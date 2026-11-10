"""The owner's actions, kept on disk in the run's events.json until the agent has handled them.

The server records each action as it happens. The agent asks for the oldest one it has not
handled (`offer`) and says it has handled it (`confirm`, through `plan-review status`). An
event is offered again until it is confirmed, so a crash between delivery and handling loses
nothing. The log only grows, so a `seq` is never reused.
"""

import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, TypeAdapter

from plan_review.paths.run_paths import RunPaths
from plan_review.utils.json_files import BrokenFile, read_file
from plan_review.utils.safe_files import file_lock, write_atomically

State = Literal["waiting", "delivered", "handled", "withdrawn"]


class Entry(BaseModel):
    seq: int
    event: dict[str, Any]
    state: State = "waiting"
    approval_withdrawn: bool = False  # delivering this review took an approval back

    @property
    def unhandled(self) -> bool:
        return self.state in ("waiting", "delivered")


class Log(BaseModel):
    events: list[Entry] = []


_Log = TypeAdapter(Log)


class EventLog:
    """Reads the file on every call, so the server and the CLI (separate processes) agree."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._approval = RunPaths(path.parent).approved

    def record(self, event: dict[str, Any]) -> None:
        with self._updating() as log:
            log.events.append(Entry(seq=len(log.events) + 1, event=event))

    def check(self) -> None:
        """Raise BrokenFile if the log could not take an event. For callers that write other
        things first and could not undo them if `record` then failed."""
        with self._updating():  # saved unchanged: only a real write proves one will work
            pass

    def offer(self) -> dict[str, Any] | None:
        """The oldest unhandled event, with its seq; None if there is none."""
        if not self._path.is_file():
            return None
        with file_lock(self._path):
            log = self._read()
            waiting = [e for e in log.events if e.unhandled]
            self._withdraw_approval(waiting)
            standing = [e for e in waiting if e.state != "withdrawn"]
            if not standing:
                return None
            first = standing[0]
            first.state = "delivered"
            self._save(log)
        offered = {**first.event, "seq": first.seq}
        if first.approval_withdrawn:
            offered["approval_withdrawn"] = True
        return offered

    def confirm(self) -> None:
        """Mark what has been delivered as handled; events that arrived since stay waiting."""
        if not self._path.is_file():
            return
        with file_lock(self._path):
            log = self._read()
            delivered = [e for e in log.events if e.state == "delivered"]
            for entry in delivered:
                entry.state = "handled"
            self._save(log)

    def _withdraw_approval(self, waiting: list[Entry]) -> None:
        """A review and an approval both waiting: the approval no longer stands."""
        approvals = [e for e in waiting if e.event.get("type") == "approved"]
        reviews = [e for e in waiting if e.event.get("type") == "review_submitted"]
        if not (approvals and reviews):
            return
        for entry in approvals:
            entry.state = "withdrawn"
        reviews[0].approval_withdrawn = True
        self._approval.unlink(missing_ok=True)

    @contextmanager
    def _updating(self) -> Generator[Log]:
        """The log to change, saved afterwards; a failure on disk is a BrokenFile, by name."""
        try:
            with file_lock(self._path):
                log = self._read()
                yield log
                self._save(log)
        except OSError as error:
            raise BrokenFile([f"{self._path.as_posix()}: can't be written: {error}"]) from error

    def _read(self) -> Log:
        return read_file(self._path, _Log) or Log()

    def _save(self, log: Log) -> None:
        write_atomically(self._path, _Log.dump_json(log, indent=2))


def wait_for_event(
    log: EventLog,
    timeout: float,
    *,
    now: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    interval: float = 0.5,
) -> dict[str, Any]:
    """The next event, as soon as there is one; `{"type": "timeout"}` after `timeout` seconds."""
    deadline = now() + timeout
    while True:
        event = log.offer()
        if event is not None:
            return event
        if now() >= deadline:
            return {"type": "timeout"}
        sleep(interval)
