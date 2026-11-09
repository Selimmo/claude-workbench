"""Push-only WebSocket audiences: viewer pages and the agent."""

from contextlib import suppress
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from plan_review.event_log import EventLog
from plan_review.file_errors import BrokenFile
from plan_review.last_event import LastEventStore


class Subscribers:
    """The sockets listening on one push-only endpoint."""

    def __init__(self) -> None:
        self._sockets: set[WebSocket] = set()

    @property
    def count(self) -> int:
        return len(self._sockets)

    def add(self, socket: WebSocket) -> None:
        self._sockets.add(socket)

    def remove(self, socket: WebSocket) -> None:
        self._sockets.discard(socket)

    async def send(self, message: dict[str, Any]) -> None:
        for socket in list(self._sockets):
            try:
                await socket.send_json(message)
            except WebSocketDisconnect, RuntimeError:
                self.remove(socket)


class AgentEvents(Subscribers):
    """What goes to the agent. Each event is first written to the run's log (for `plan-review
    wait`) and kept (for a Resend), then pushed to any connected socket."""

    def __init__(self, kept: LastEventStore, log: EventLog) -> None:
        super().__init__()
        self._kept = kept
        self._log = log

    def check_log(self) -> None:
        """Raise BrokenFile now if `record` could not reach the log."""
        self._log.check()

    def record(self, message: dict[str, Any]) -> None:
        # The log is how the agent gets the event, so a broken one stops everything here. Only
        # then is it kept: a Resend must never offer an event the log refused.
        self._log.record(message)
        with suppress(BrokenFile, OSError):  # a Resend is an extra, not worth losing it over
            self._kept.keep(message)

    async def push(self, message: dict[str, Any]) -> None:
        await super().send(message)

    async def send(self, message: dict[str, Any]) -> None:
        self.record(message)
        await self.push(message)

    async def resend(self, message: dict[str, Any]) -> None:
        """Send a kept event again: the log already holds it, and must not get it twice."""
        self._kept.keep(message)
        await self.push(message)
