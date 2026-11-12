"""What a detached viewer does while it runs and when it ends.

A CLI with no background watcher needs the viewer to run without one: `plan-review serve
--detach` starts it on its own and `plan-review stop` ends it. This module holds what the
viewer's own process adds to its server: when an unused viewer stops itself, who it is, and
how to stop it.
"""

import asyncio
import os
import time
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from filelock import Timeout

from plan_review.events.subscribers import Subscribers
from plan_review.viewer.client import TOKEN_HEADER
from plan_review.viewer.record import ViewerInfo, ViewerRecord

IDLE_LIMIT = 2 * 3600.0  # seconds a viewer may run with no page open
RECORD_LOCK_WAIT = 1.0  # seconds an ending viewer waits to take viewer.json's lock


class IdleWatch:
    """Says when a viewer has had no page open for the idle limit.

    The clock starts when the viewer starts and again each time the last page closes; it
    stops while any page is open.
    """

    def __init__(self, started: float, limit: float = IDLE_LIMIT) -> None:
        self._empty_since: float | None = started
        self._limit = limit

    def expired(self, open_pages: int, *, now: float) -> bool:
        if open_pages > 0:
            self._empty_since = None
            return False
        if self._empty_since is None:
            self._empty_since = now
        return now - self._empty_since >= self._limit


@dataclass
class ViewerLifetime:
    """What a detached viewer's server needs to know about its own process."""

    run_id: str
    token: str
    request_stop: Callable[[], None]
    record: ViewerRecord  # viewer.json: removed when this viewer ends
    idle_limit: float = IDLE_LIMIT
    check_every: float = 30.0

    def announce(self, port: int) -> None:
        """Write viewer.json: this process is up on `port`.

        Takes no lock: the launcher holds it for the whole start, waiting for this write.
        """
        self.record.write(
            ViewerInfo(run_id=self.run_id, pid=os.getpid(), port=port, token=self.token)
        )

    def routes(self) -> APIRouter:
        router = APIRouter()

        @router.get("/api/viewer")
        def who() -> dict[str, object]:  # pyright: ignore[reportUnusedFunction]
            return {"run_id": self.run_id, "pid": os.getpid()}

        @router.post("/api/stop")
        def stop(request: Request) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
            if request.headers.get(TOKEN_HEADER) != self.token:
                return JSONResponse({"errors": ["wrong token"]}, status_code=403)
            self.request_stop()
            return JSONResponse({"stopping": True})

        return router

    async def _stop_when_idle(self, pages: Subscribers) -> None:
        watch = IdleWatch(time.monotonic(), self.idle_limit)
        while True:
            await asyncio.sleep(self.check_every)
            if watch.expired(pages.count, now=time.monotonic()):
                self.request_stop()
                return

    @asynccontextmanager
    async def watching(self, pages: Subscribers) -> AsyncGenerator[None]:
        """For the life of the server: stop it when idle, and forget the record when it ends."""
        idle = asyncio.create_task(self._stop_when_idle(pages))
        try:
            yield
        finally:
            idle.cancel()
            with suppress(asyncio.CancelledError):
                await idle
            self._forget_record()

    def _forget_record(self) -> None:
        # Not a long wait: the command starting this viewer holds the lock until the viewer
        # answers or fails. Whoever holds it starts or stops a viewer and sees to the record.
        with suppress(Timeout), self.record.locked(timeout=RECORD_LOCK_WAIT):
            self.record.remove_if_mine(self.token)
