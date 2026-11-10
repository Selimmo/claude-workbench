"""What goes to the agent: logged, kept for a Resend, and pushed to connected sockets."""

from contextlib import suppress
from typing import Any

from fastapi import WebSocket

from plan_review.events.event_log import EventLog
from plan_review.events.last_event import LastEventStore
from plan_review.events.subscribers import Subscribers
from plan_review.utils.json_files import BrokenFile


class AgentEvents:
    """What goes to the agent. Each event is first written to the run's log (for `plan-review
    wait`) and kept (for a Resend), then pushed to any connected socket."""

    def __init__(self, kept: LastEventStore, log: EventLog) -> None:
        self._subscribers = Subscribers()
        self._kept = kept
        self._log = log

    def add(self, socket: WebSocket) -> None:
        self._subscribers.add(socket)

    def remove(self, socket: WebSocket) -> None:
        self._subscribers.remove(socket)

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
        await self._subscribers.send(message)

    async def send(self, message: dict[str, Any]) -> None:
        self.record(message)
        await self.push(message)

    async def resend(self, message: dict[str, Any]) -> None:
        """Send a kept event again: the log already holds it, and must not get it twice."""
        self._kept.keep(message)
        await self.push(message)
