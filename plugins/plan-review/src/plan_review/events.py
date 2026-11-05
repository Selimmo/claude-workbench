"""Push-only WebSocket audiences: viewer pages and Claude."""

from contextlib import suppress
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from plan_review.file_errors import BrokenFile
from plan_review.last_event import LastEventStore


class Subscribers:
    """The sockets listening on one push-only endpoint."""

    def __init__(self) -> None:
        self._sockets: set[WebSocket] = set()

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


class ClaudeEvents(Subscribers):
    """What goes to Claude: each event is kept first, so a Resend can send it again."""

    def __init__(self, kept: LastEventStore) -> None:
        super().__init__()
        self._kept = kept

    async def send(self, message: dict[str, Any]) -> None:
        with suppress(BrokenFile):  # the event is more urgent than keeping it for a resend
            self._kept.keep(message)
        await super().send(message)
