"""Starting, stopping and finding a run's detached viewer process."""

import secrets
import subprocess
import sys
import time
from pathlib import Path
from typing import Protocol

from plan_review.paths.run_paths import RunPaths
from plan_review.viewer.client import ViewerClient
from plan_review.viewer.record import ViewerInfo, ViewerRecord

READY_TIMEOUT = 30.0  # seconds to wait for a new viewer to answer
READY_POLL = 0.1


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


class ProcessSpawner:
    """Starting a process on each OS."""

    def command(self, run_id: str, token: str) -> list[str]:
        """Port 0: the viewer picks its own free port and says which in viewer.json."""
        return [
            sys.executable,
            "-m",
            "plan_review.cli",
            "viewer-process",
            run_id,
            "--port",
            "0",
            "--token",
            token,
        ]

    def spawn(self, root: Path, run_id: str, token: str, log: Path) -> Spawned:
        """Start the viewer in a process of its own, in its own session, writing to `log`."""
        command = self.command(run_id, token)
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


class ViewerLauncher:
    def __init__(self, work: Path, run_id: str) -> None:
        self._work = work
        self._run_id = run_id
        self._record = ViewerRecord(work)
        self._spawner = ProcessSpawner()
        self._client = ViewerClient()

    def running(self) -> ViewerInfo | None:
        """The run's viewer if its record is there and it answers."""
        info = self._record.read()
        if info is None:
            return None
        return info if self._client.answers_as(info.port, self._run_id) else None

    def start(self, root: Path) -> tuple[ViewerInfo, bool]:
        """The run's viewer, started if it was not running; and whether this call started it."""
        with self._record.locked():  # two starts at once make one viewer
            existing = self.running()
            if existing is not None:
                return existing, False
            stale = self._record.read()
            if stale is not None:
                self._record.remove_if_mine(stale.token)  # it doesn't answer: not a viewer
            token, log = secrets.token_hex(16), RunPaths(self._work).viewer_log
            process = self._spawner.spawn(root, self._run_id, token, log)
            deadline = time.monotonic() + READY_TIMEOUT
            while True:
                info = self._record.read()  # written by the viewer once it is listening
                if (
                    info is not None
                    and info.token == token
                    and self._client.answers_as(info.port, self._run_id)
                ):
                    return info, True
                code = process.poll()
                if code is not None or time.monotonic() >= deadline:
                    reason = ""
                    if code is None:
                        process.kill()  # first: once the record is gone nothing could find it
                        reason = f"the viewer did not answer within {READY_TIMEOUT:g} seconds\n"
                    self._record.remove_if_mine(token)
                    text = log.read_text(errors="replace") if log.is_file() else ""
                    raise ViewerFailed(code if code is not None else 1, reason + text)
                time.sleep(READY_POLL)

    def stop(self) -> bool:
        """End the run's viewer and drop its record; False if there was nothing to stop."""
        info = self._record.read()
        if info is None:
            return False
        if self._client.answers_as(info.port, self._run_id):  # the token goes only to this run
            self._client.post_stop(info.port, info.token)
            deadline = time.monotonic() + READY_TIMEOUT
            while self._client.answers_as(info.port, self._run_id) and time.monotonic() < deadline:
                time.sleep(READY_POLL)
        # Only around this last look: the wait above can take as long as READY_TIMEOUT.
        with self._record.locked():
            self._record.remove_if_mine(info.token)
        return True
