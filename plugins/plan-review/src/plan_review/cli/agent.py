"""What the agent says to the owner and hears back: wait, status, reply, threads."""

import json
import math
import sys
from pathlib import Path

from plan_review.cli.runtime import Runtime, project
from plan_review.events.event_log import EventLog
from plan_review.events.status import StatusStore, set_status
from plan_review.paths.run_id import label
from plan_review.paths.run_paths import RunPaths
from plan_review.review.threads import ThreadNotFound, ThreadStore
from plan_review.utils.text import BlankComment


def _existing_work_dir(run_id: str, runtime: Runtime) -> Path | None:
    """The run's folder; None (after saying so) if there is none, e.g. a wrong directory."""
    work = runtime.work_dir(project(), run_id)
    if work.is_dir():
        return work
    print(
        f"no {work.as_posix()}/ for {label(run_id)}: is this the project root?",
        file=sys.stderr,
    )
    return None


def threads(run_id: str, *, runtime: Runtime) -> int:
    open_threads = [
        t
        for t in ThreadStore(RunPaths(runtime.work_dir(project(), run_id)).comments).all()
        if not t.resolved
    ]
    print(json.dumps([t.model_dump(mode="json") for t in open_threads], indent=2))
    return 0


def reply(run_id: str, thread_id: str, text: str, *, runtime: Runtime) -> int:
    comments = RunPaths(runtime.work_dir(project(), run_id)).comments
    try:
        ThreadStore(comments).reply(thread_id, text, author="agent")
    except ThreadNotFound:
        print(f"no thread '{thread_id}' for {label(run_id)}", file=sys.stderr)
        return 1
    except BlankComment as error:
        print(error, file=sys.stderr)
        return 1
    print(f"replied to {thread_id}")
    return 0


def wait(run_id: str, timeout: str, *, runtime: Runtime) -> int:
    try:
        seconds = float(timeout)
        if not 0 <= seconds < math.inf:
            raise ValueError(timeout)
    except ValueError:
        print(
            f"plan-review wait: --timeout must be a number of seconds, not '{timeout}'",
            file=sys.stderr,
        )
        return 2
    work = _existing_work_dir(run_id, runtime)
    if work is None:
        return 1
    event = runtime.wait_for_event(EventLog(RunPaths(work).events), seconds)
    print(json.dumps(event, separators=(",", ":")), flush=True)
    return 0


def status(run_id: str, text: str, *, done: bool, clear: bool, runtime: Runtime) -> int:
    work = _existing_work_dir(run_id, runtime)
    if work is None:
        return 1
    if not clear and not text.strip():
        print("status text is empty", file=sys.stderr)  # before anything is moved aside
        return 1
    paths = RunPaths(work)
    store = StatusStore(paths.status)
    try:
        moved = store.set_aside()
        if moved:
            print(
                f"{store.path.as_posix()} was broken: moved to {moved.as_posix()}", file=sys.stderr
            )
        if clear:
            store.clear()
        else:
            problems = set_status(store, EventLog(paths.events), text, done=done)
            if problems:
                print("\n".join(problems), file=sys.stderr)  # the status is written all the same
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    return 0
