"""Push-only WebSocket audiences: viewer pages and Claude."""

from typing import Any

from fastapi import WebSocket, WebSocketDisconnect


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
            except (WebSocketDisconnect, RuntimeError):
                self.remove(socket)
