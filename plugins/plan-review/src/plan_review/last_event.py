"""The last event sent to the agent, kept so it can be sent again.

`/events` is fire-and-forget: an event sent before the agent's watcher connects is lost.
Keeping the latest one in the issue's last_event.json lets the viewer offer a Resend.
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, TypeAdapter

from plan_review.file_errors import read_file
from plan_review.status import Status
from plan_review.threads import write_atomically


class LastEvent(BaseModel):
    event: dict[str, Any]  # exactly what went to /events
    sent_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


_LastEvent = TypeAdapter(LastEvent)


class LastEventStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def get(self) -> LastEvent | None:
        return read_file(self._path, _LastEvent)

    def keep(self, event: dict[str, Any]) -> LastEvent:
        self.get()  # a broken file is reported, never replaced
        last = LastEvent(event=event)
        write_atomically(self._path, last.model_dump_json(indent=2).encode())
        return last


def answered(status: Status | None, last: LastEvent) -> bool:
    """Whether the agent set a status after the event was sent (an older one is a past round's)."""
    return status is not None and status.at > last.sent_at
