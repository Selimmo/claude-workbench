"""The `plan-review` command line."""

import argparse
import json
import socket
import sys
import webbrowser
from collections.abc import Callable
from datetime import date
from importlib.metadata import version
from pathlib import Path

import uvicorn
from fastapi import FastAPI

from plan_review.orchestration import MalformedReview, branch_name, tree_hash, verdict
from plan_review.pipeline import PipelineConfigError, load_pipeline
from plan_review.plan import Plan, PlanFileError, load_plan, record_branch
from plan_review.run_id import InvalidRunId, check_run_id, label
from plan_review.server import create_app
from plan_review.status import StatusStore
from plan_review.threads import BlankComment, ThreadNotFound, ThreadStore
from plan_review.upgrade import upgrade
from plan_review.workdir import ensure_work_dir, new_prompt_work_dir, work_dir

STATIC_DIR = Path(__file__).parent / "static"


def _schema() -> int:
    print(json.dumps(Plan.model_json_schema(), indent=2))
    return 0


def _tree_hash() -> int:
    print(tree_hash(Path.cwd()))
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="plan-review")
    # Handled here rather than with action="version", which calls sys.exit():
    # main() returns its exit code so callers (and tests) stay in control.
    parser.add_argument("--version", action="store_true", help="print the version and exit")
    commands = parser.add_subparsers(dest="command")

    def command(
        name: str, help: str, run: Callable[[argparse.Namespace], int]
    ) -> argparse.ArgumentParser:
        sub = commands.add_parser(name, help=help)
        sub.set_defaults(run=run)
        return sub

    command("schema", "print the plan.json JSON Schema", lambda a: _schema())
    init = command(
        "init",
        "create a run's .claude/work/<id>/ folder (or --prompt <name>: <name>-<date>)",
        lambda a: _init(a.run_id, a.prompt),
    )
    init.add_argument("run_id", nargs="?", help="an issue number or key, e.g. 42 or PROJ-123")
    init.add_argument("--prompt", metavar="NAME", help="start a prompt run named NAME-<today>")
    command("validate", "check a plan.json file", lambda a: _validate(a.file)).add_argument(
        "file", type=Path
    )
    serve = command("serve", "open the viewer for a run's plan", lambda a: _serve(a.run_id, a.open))
    serve.add_argument("run_id")
    serve.add_argument(
        "--open",
        choices=["browser", "none"],
        help="open the default browser, or only print the URL "
        "(default: viewer.open in .claude/pipeline.json, else browser)",
    )
    command(
        "config", "print this project's pipeline settings, defaults filled in", lambda a: _config()
    )
    command(
        "threads", "list a run's open comment threads as JSON", lambda a: _threads(a.run_id)
    ).add_argument("run_id")
    reply = command(
        "reply",
        "answer a comment thread as Claude",
        lambda a: _reply(a.run_id, a.thread_id, a.text),
    )
    reply.add_argument("run_id")
    reply.add_argument("thread_id")
    reply.add_argument("text")
    status = command(
        "status",
        "show the owner what Claude is doing with their review (latest text wins)",
        lambda a: _status(a.run_id, a.text, done=a.done, clear=a.clear),
    )
    status.add_argument("run_id")
    status.add_argument("text", nargs="?", default="")
    status.add_argument("--done", action="store_true", help="mark it finished")
    status.add_argument("--clear", action="store_true", help="remove the status line")
    command(
        "branch",
        "the branch name for a run: recorded in its plan, else made",
        lambda a: _branch(a.run_id),
    ).add_argument("run_id")
    command(
        "verdict",
        "a review's verdict: exit 0 PASS, 1 FINDINGS, 2 malformed",
        lambda a: _verdict(a.file),
    ).add_argument("file", type=Path)
    command("upgrade", "update the installed plugin to its newest release", lambda a: upgrade())
    command("tree-hash", "fingerprint of uncommitted changes (git)", lambda a: _tree_hash())
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.version:
        print(f"plan-review {version('plan-review')}")
        return 0
    run: Callable[[argparse.Namespace], int] | None = getattr(args, "run", None)
    # Checked here, not as an argparse `type`: a failed type check calls sys.exit().
    run_id: str | None = getattr(args, "run_id", None)
    if run_id is not None:
        try:
            check_run_id(run_id)
        except InvalidRunId as error:
            print(error, file=sys.stderr)
            return 2
    return run(args) if run else 0


PIPELINE_FILE = Path(".claude", "pipeline.json")


def _config() -> int:
    try:
        config = load_pipeline(PIPELINE_FILE)
    except PipelineConfigError as error:
        print("\n".join(error.errors), file=sys.stderr)
        return 1
    print(config.model_dump_json(indent=2))
    return 0


def _work_dir(run_id: str) -> Path:
    """Where a run's plan, comments and reports live, relative to the project root."""
    return work_dir(Path(), run_id)


def today() -> date:
    return date.today()


def _init(run_id: str | None, prompt: str | None) -> int:
    if (run_id is None) == (prompt is None):
        print("plan-review init: give either a run id or --prompt <name>", file=sys.stderr)
        return 2
    if prompt is not None:
        try:
            check_run_id(f"{prompt}-{today().isoformat()}")
        except InvalidRunId as error:
            print(error, file=sys.stderr)
            return 2
        print(new_prompt_work_dir(Path(), prompt, today()).as_posix())
        return 0
    assert run_id is not None
    print(ensure_work_dir(Path(), run_id).as_posix())
    return 0


def _validate(file: Path) -> int:
    try:
        plan = load_plan(file)
    except PlanFileError as error:
        print("\n".join(error.errors), file=sys.stderr)
        return 2 if error.missing else 1
    print(f"OK: plan for {label(plan.issue.id)} ({len(plan.element_ids())} elements)")
    return 0


def _serve(run_id: str, open_flag: str | None) -> int:
    try:
        open_mode = open_flag or load_pipeline(PIPELINE_FILE).viewer.open
    except PipelineConfigError as error:
        print("\n".join(error.errors), file=sys.stderr)
        return 1
    if not (STATIC_DIR / "index.html").is_file():
        print(
            f"{STATIC_DIR.as_posix()}: viewer page not built; run `npm --prefix web run build`",
            file=sys.stderr,
        )
        return 2
    plan_file = _work_dir(run_id) / "plan.json"
    try:
        load_plan(plan_file)
    except PlanFileError as error:
        print("\n".join(error.errors), file=sys.stderr)
        return 2 if error.missing else 1
    ensure_work_dir(Path(), run_id)  # the page writes comments and drafts there
    # Bind and listen before opening the browser: its first request then waits in the
    # socket's queue until uvicorn accepts it, instead of racing the server's startup.
    # Port 0 lets the OS pick a free port.
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen()
        url = f"http://127.0.0.1:{sock.getsockname()[1]}/"
        print(f"plan-review: {label(run_id)} at {url} (Ctrl+C to stop)", flush=True)
        if open_mode == "browser":
            webbrowser.open(url)
        run_server(create_app(plan_file, STATIC_DIR), sock)
    return 0


def _threads(run_id: str) -> int:
    open_threads = [
        t for t in ThreadStore(_work_dir(run_id) / "comments.json").all() if not t.resolved
    ]
    print(json.dumps([t.model_dump(mode="json") for t in open_threads], indent=2))
    return 0


def _status(run_id: str, text: str, *, done: bool, clear: bool) -> int:
    work = _work_dir(run_id)
    if not work.is_dir():
        print(
            f"no {work.as_posix()}/ for {label(run_id)}: is this the project root?",
            file=sys.stderr,
        )
        return 1
    store = StatusStore(work / "status.json")
    if clear:
        store.clear()
        return 0
    try:
        store.set(text, done=done)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    return 0


def _reply(run_id: str, thread_id: str, text: str) -> int:
    try:
        ThreadStore(_work_dir(run_id) / "comments.json").reply(thread_id, text, author="claude")
    except ThreadNotFound:
        print(f"no thread '{thread_id}' for {label(run_id)}", file=sys.stderr)
        return 1
    except BlankComment as error:
        print(error, file=sys.stderr)
        return 1
    print(f"replied to {thread_id}")
    return 0


def run_server(app: FastAPI, sock: socket.socket) -> None:
    uvicorn.Server(uvicorn.Config(app, log_level="warning")).run(sockets=[sock])


def _verdict(file: Path) -> int:
    try:
        result = verdict(file)
    except MalformedReview as error:
        print(error, file=sys.stderr)
        return 2
    print(result)
    return 0 if result == "PASS" else 1


def _branch(run_id: str) -> int:
    plan_file = _work_dir(run_id) / "plan.json"
    try:
        plan = load_plan(plan_file)
        if plan.branch:  # already named (and maybe created): never name it again
            print(plan.branch)
            return 0
        pattern = load_pipeline(PIPELINE_FILE).branch
    except (PlanFileError, PipelineConfigError) as error:
        print("\n".join(error.errors), file=sys.stderr)
        return 1
    branch = branch_name(run_id, plan.issue, pattern)
    record_branch(plan_file, branch)
    print(branch)
    return 0
