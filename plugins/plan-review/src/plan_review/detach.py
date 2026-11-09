"""A viewer that runs as its own process: it outlives the command that started it.

A CLI with no background watcher needs the viewer to run without one: `plan-review serve
--detach` starts it on its own and `plan-review stop` ends it. This module holds what that
needs: when an unused viewer stops itself, and what the detached viewer's server adds (who
it is, how to stop it).
"""

import asyncio
import json
import os
import secrets
import socket
import subprocess
import sys
import time
import urllib.request
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from filelock import Timeout
from pydantic import BaseModel, TypeAdapter

from plan_review.events import Subscribers
from plan_review.file_errors import read_file
from plan_review.threads import file_lock, write_atomically

IDLE_LIMIT = 2 * 3600.0  # seconds a viewer may run with no page open
RECORD_LOCK_WAIT = 1.0  # seconds an ending viewer waits to take viewer.json's lock
TOKEN_HEADER = "x-plan-review-token"


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


def _remove_unless_replaced(record: Path, token: str) -> None:
    """Remove viewer.json if it is still this viewer's (a newer viewer's is left alone)."""
    try:
        held = json.loads(record.read_text()).get("token")
    except OSError, ValueError, AttributeError:
        held = None
    if held in (None, token):
        record.unlink(missing_ok=True)


@dataclass
class DetachedViewer:
    """What a detached viewer's server needs to know about its own process."""

    run_id: str
    token: str
    request_stop: Callable[[], None]
    record: Path  # viewer.json: removed when this viewer ends
    idle_limit: float = IDLE_LIMIT
    check_every: float = 30.0

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
        with suppress(Timeout), file_lock(self.record, timeout=RECORD_LOCK_WAIT):
            _remove_unless_replaced(self.record, self.token)


# --- starting and stopping the process ---------------------------------------------------

READY_TIMEOUT = 30.0  # seconds to wait for a new viewer to answer
READY_POLL = 0.1


class ViewerRecord(BaseModel):
    """viewer.json: which process and port a run's detached viewer has, and the stop token."""

    run_id: str
    pid: int
    port: int
    token: str


_Record = TypeAdapter(ViewerRecord)


class Spawned(Protocol):
    pid: int

    def poll(self) -> int | None: ...

    def kill(self) -> None: ...


class ViewerFailed(Exception):
    """The viewer process ended before it answered."""

    def __init__(self, code: int, log: str) -> None:
        super().__init__(log)
        self.code = code
        self.log = log


def record_file(work: Path) -> Path:
    return work / "viewer.json"


def answers_as(port: int, run_id: str) -> bool:
    """Is it this run's viewer that answers on `port`?"""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/viewer", timeout=2) as reply:
            return json.load(reply).get("run_id") == run_id
    except OSError, ValueError, AttributeError:
        return False


def post_stop(port: int, token: str) -> None:
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/stop", method="POST", headers={TOKEN_HEADER: token}
    )
    with suppress(OSError):
        urllib.request.urlopen(request, timeout=5).close()


def spawn_viewer(root: Path, run_id: str, port: int, token: str, log: Path) -> Spawned:
    """Start the viewer in a process of its own, in its own session, writing to `log`."""
    command = [
        sys.executable,
        "-m",
        "plan_review.cli",
        "viewer-process",
        run_id,
        "--port",
        str(port),
        "--token",
        token,
    ]
    with log.open("wb") as out:
        if sys.platform == "win32":
            flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            return subprocess.Popen(
                command,
                cwd=root,
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=subprocess.STDOUT,
                creationflags=flags,
            )
        return subprocess.Popen(
            command,
            cwd=root,
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def running_viewer(work: Path, run_id: str) -> ViewerRecord | None:
    """The run's viewer if its record is there and it answers."""
    record = read_file(record_file(work), _Record)
    if record is None:
        return None
    return record if answers_as(record.port, run_id) else None


def start_viewer(root: Path, work: Path, run_id: str) -> tuple[ViewerRecord, bool]:
    """The run's viewer, started if it was not running; and whether this call started it."""
    with file_lock(record_file(work)):  # two starts at once make one viewer
        existing = running_viewer(work, run_id)
        if existing is not None:
            return existing, False
        port, token, log = _free_port(), secrets.token_hex(16), work / "viewer.log"
        process = spawn_viewer(root, run_id, port, token, log)
        record = ViewerRecord(run_id=run_id, pid=process.pid, port=port, token=token)
        write_atomically(record_file(work), _Record.dump_json(record, indent=2))
        deadline = time.monotonic() + READY_TIMEOUT
        while not answers_as(port, run_id):
            code = process.poll()
            if code is not None or time.monotonic() >= deadline:
                reason = ""
                if code is None:
                    process.kill()  # first: once the record is gone nothing could find it
                    reason = f"the viewer did not answer within {READY_TIMEOUT:g} seconds\n"
                record_file(work).unlink(missing_ok=True)
                text = log.read_text(errors="replace") if log.is_file() else ""
                raise ViewerFailed(code if code is not None else 1, reason + text)
            time.sleep(READY_POLL)
        return record, True


def stop_viewer(work: Path, run_id: str) -> bool:
    """End the run's viewer and drop its record; False if there was nothing to stop."""
    record = read_file(record_file(work), _Record)
    if record is None:
        return False
    if answers_as(record.port, run_id):  # the token goes only to this run's own viewer
        post_stop(record.port, record.token)
        deadline = time.monotonic() + READY_TIMEOUT
        while answers_as(record.port, run_id) and time.monotonic() < deadline:
            time.sleep(READY_POLL)
    # Only around this last look: the wait above can take as long as READY_TIMEOUT.
    with file_lock(record_file(work)):
        _remove_unless_replaced(record_file(work), record.token)
    return True
