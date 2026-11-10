"""What a command takes from the outside world, so tests can hand in their own."""

import socket
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI

from plan_review.events import waiter
from plan_review.events.event_log import EventLog
from plan_review.paths import workdir

STATIC_DIR = Path(__file__).parent.parent / "static"  # the built viewer page


def run_server(app: FastAPI, sock: socket.socket) -> None:
    uvicorn.Server(uvicorn.Config(app, log_level="warning")).run(sockets=[sock])


@dataclass(frozen=True)
class Runtime:
    """The real ones are the defaults. Data only: the commands stay plain functions."""

    work_dir: Callable[[Path, str], Path] = workdir.work_dir
    ensure_work_dir: Callable[[Path, str], Path] = workdir.ensure_work_dir
    today: Callable[[], date] = date.today
    static_dir: Path = STATIC_DIR
    run_server: Callable[[FastAPI, socket.socket], None] = run_server
    open_browser: Callable[[str], object] = webbrowser.open
    wait_for_event: Callable[[EventLog, float], dict[str, Any]] = waiter.wait_for_event
