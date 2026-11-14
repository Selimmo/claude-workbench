"""What a command takes from the outside world, so tests can hand in their own."""

import socket
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Protocol

import uvicorn
from fastapi import FastAPI

from plan_review.events import waiter
from plan_review.events.event_log import EventLog
from plan_review.paths import workdir
from plan_review.paths.project_root import project_root
from plan_review.settings.user_folder import user_config_dir

STATIC_DIR = Path(__file__).parent.parent / "static"  # the built viewer page


def project() -> Path:
    """The folder every command reads `.plan-review/` from: the project root, found from here.

    Run from the root itself it stays the relative `Path()`, so the paths commands print are the
    same short ones as before; from a subfolder it is the root's absolute path.
    """
    here = Path.cwd().resolve()
    root = project_root(here, user_config_dir())
    return Path() if root == here else root


class ServerStop:
    """Lets the app end the server it runs in, without knowing about uvicorn.

    Handed to the app as a plain callable and to `run_server`, which attaches the server.
    """

    def __init__(self) -> None:
        self._server: uvicorn.Server | None = None
        self._asked = False

    def attach(self, server: uvicorn.Server) -> None:
        self._server = server
        if self._asked:
            server.should_exit = True

    def __call__(self) -> None:
        self._asked = True
        if self._server is not None:
            self._server.should_exit = True


class ServerRunner(Protocol):
    def __call__(
        self, app: FastAPI, sock: socket.socket, stop: ServerStop | None = None, /
    ) -> None: ...


def run_server(app: FastAPI, sock: socket.socket, stop: ServerStop | None = None) -> None:
    """The one place uvicorn is started."""
    server = uvicorn.Server(uvicorn.Config(app, log_level="warning"))
    if stop is not None:
        stop.attach(server)
    server.run(sockets=[sock])


@dataclass(frozen=True)
class Runtime:
    """The real ones are the defaults. Data only: the commands stay plain functions."""

    work_dir: Callable[[Path, str], Path] = workdir.work_dir
    ensure_work_dir: Callable[[Path, str], Path] = workdir.ensure_work_dir
    today: Callable[[], date] = date.today
    static_dir: Path = STATIC_DIR
    run_server: ServerRunner = run_server
    open_browser: Callable[[str], object] = webbrowser.open
    wait_for_event: Callable[[EventLog, float], dict[str, Any]] = waiter.wait_for_event
