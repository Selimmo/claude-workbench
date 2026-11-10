"""The sockets listening on a push-only endpoint."""

from typing import Any, Protocol

from fastapi import WebSocket, WebSocketDisconnect


class Listeners(Protocol):
    """Anything a socket can be added to and removed from."""

    def add(self, socket: WebSocket) -> None: ...

    def remove(self, socket: WebSocket) -> None: ...


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
