"""The `plan-review` command line."""

import argparse
import json
import math
import socket
import sys
import webbrowser
from collections.abc import Callable
from datetime import date
from importlib.metadata import version
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from pydantic import ValidationError

from plan_review.events.event_log import EventLog, wait_for_event
from plan_review.events.status import StatusStore
from plan_review.grill.decisions_md import decisions_markdown
from plan_review.grill.drafts import GrillDraftStore
from plan_review.grill.grill import GrillError, GrillStore
from plan_review.grill.turn import Turn
from plan_review.harness.adapters import ADAPTERS, adapter_by_key
from plan_review.harness.upgrade import upgrade
from plan_review.paths.run_id import InvalidRunId, check_run_id, label
from plan_review.paths.run_paths import RunPaths
from plan_review.paths.workdir import (
    ensure_work_dir,
    new_prompt_work_dir,
    preferences_file,
    work_dir,
)
from plan_review.pipeline.orchestration import MalformedReview, branch_name, tree_hash, verdict
from plan_review.plan.plan import Plan, PlanFileError, load_plan, record_branch, shape_problems
from plan_review.review.threads import ThreadNotFound, ThreadStore
from plan_review.settings.migration import config_source, preferences_source
from plan_review.settings.pipeline_config import PipelineConfig, PipelineConfigError, load_pipeline
from plan_review.settings.prefs import GrillMode, grill_mode, load_preferences, record
from plan_review.utils.json_files import BrokenFile, named_errors
from plan_review.utils.text import BlankComment
from plan_review.viewer.app import create_app
from plan_review.viewer.detach import (
    DetachedViewer,
    ViewerFailed,
    record_file,
    start_viewer,
    stop_viewer,
)

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
    commands = parser.add_subparsers(dest="command", metavar="command")

    def command(
        name: str, help: str | None, run: Callable[[argparse.Namespace], int]
    ) -> argparse.ArgumentParser:
        # No `help=` at all hides a subcommand from the listing; `help=None` would not.
        sub = commands.add_parser(name) if help is None else commands.add_parser(name, help=help)
        sub.set_defaults(run=run)
        return sub

    command("schema", "print the plan.json JSON Schema", lambda a: _schema())
    init = command(
        "init",
        "create a run's .plan-review/work/<id>/ folder (or --prompt <name>: <name>-<date>)",
        lambda a: _init(a.run_id, a.prompt),
    )
    init.add_argument("run_id", nargs="?", help="an issue number or key, e.g. 42 or PROJ-123")
    init.add_argument("--prompt", metavar="NAME", help="start a prompt run named NAME-<today>")
    command("validate", "check a plan.json file", lambda a: _validate(a.file)).add_argument(
        "file", type=Path
    )
    serve = command(
        "serve",
        "open the viewer for a run's plan",
        lambda a: _serve(a.run_id, a.open, detach=a.detach),
    )
    serve.add_argument("run_id")
    serve.add_argument(
        "--detach",
        action="store_true",
        help="run the viewer as its own process and return (stop it with `plan-review stop`)",
    )
    serve.add_argument(
        "--open",
        choices=["browser", "none"],
        help="open the default browser, or only print the URL "
        "(default: viewer.open in .plan-review/config.json, else browser)",
    )
    install = command(
        "install",
        "put plan-review's skill and agents where a CLI reads them",
        lambda a: _install(a.cli),
    )
    install.add_argument("cli", choices=[a.key for a in ADAPTERS])
    command("stop", "stop a run's detached viewer", lambda a: _stop(a.run_id)).add_argument(
        "run_id"
    )
    process = command("viewer-process", None, lambda a: _viewer_process(a))
    process.add_argument("run_id")
    process.add_argument("--port", type=int, required=True)
    process.add_argument("--token", required=True)
    command(
        "config", "print this project's pipeline settings, defaults filled in", lambda a: _config()
    )
    command(
        "threads", "list a run's open comment threads as JSON", lambda a: _threads(a.run_id)
    ).add_argument("run_id")
    reply = command(
        "reply",
        "answer a comment thread as the agent",
        lambda a: _reply(a.run_id, a.thread_id, a.text),
    )
    reply.add_argument("run_id")
    reply.add_argument("thread_id")
    reply.add_argument("text")
    status = command(
        "status",
        "show the owner what the agent is doing with their review (latest text wins)",
        lambda a: _status(a.run_id, a.text, done=a.done, clear=a.clear),
    )
    status.add_argument("run_id")
    status.add_argument("text", nargs="?", default="")
    status.add_argument("--done", action="store_true", help="mark it finished")
    status.add_argument("--clear", action="store_true", help="remove the status line")
    wait = command(
        "wait",
        'the next thing the owner did, as one JSON line; {"type":"timeout"} if nothing',
        lambda a: _wait(a.run_id, a.timeout),
    )
    wait.add_argument("run_id")
    wait.add_argument(
        "--timeout", default="240", metavar="SECONDS", help="how long to wait (default: 240)"
    )
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
    grill = command(
        "grill", "the page grill: post turns, see what is pending", lambda a: _usage(grill)
    )
    grill_commands = grill.add_subparsers(dest="grill_command")

    def grill_command(
        name: str, help: str, run: Callable[[argparse.Namespace], int]
    ) -> argparse.ArgumentParser:
        sub = grill_commands.add_parser(name, help=help)
        sub.set_defaults(run=run)
        return sub

    post = grill_command(
        "post",
        "add the agent's next turn to a run's grill.json",
        lambda a: _grill_post(a.run_id, a.file),
    )
    post.add_argument("run_id")
    post.add_argument("file", type=Path, help="the turn, as JSON (see `grill schema`)")
    pending = grill_command(
        "pending",
        "whether the owner confirmed, and what they did that is not answered yet (JSON)",
        lambda a: _grill_pending(a.run_id),
    )
    pending.add_argument("run_id")
    decisions = grill_command(
        "decisions",
        "write W/decisions.md from the confirmed grill",
        lambda a: _grill_decisions(a.run_id),
    )
    decisions.add_argument("run_id")
    grill_command("schema", "print the JSON Schema of a turn", lambda a: _grill_schema())
    prefs = command(
        "prefs",
        "the owner's recorded choices: `prefs grill [page|chat]` sets or prints the grill mode",
        lambda a: _prefs(a.setting, a.value),
    )
    prefs.add_argument("setting", choices=["grill"])
    prefs.add_argument("value", nargs="?", help="page or chat; leave out to print the mode")
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
    if run is None:
        return 0
    try:
        return run(args)
    except BrokenFile as error:
        print("\n".join(error.errors), file=sys.stderr)
        return 1


def _pipeline() -> tuple[PipelineConfig, str | None]:
    """The project's settings, and a hint to show when they came from an old file."""
    source = config_source(Path())
    return load_pipeline(source.path), source.move_hint


def _hint(line: str | None) -> None:
    if line is not None:
        print(line, file=sys.stderr)


def _usage(parser: argparse.ArgumentParser) -> int:
    parser.print_help(sys.stderr)
    return 2


def _config() -> int:
    try:
        config, hint = _pipeline()
    except PipelineConfigError as error:
        print("\n".join(error.errors), file=sys.stderr)
        return 1
    print(config.model_dump_json(indent=2))
    _hint(hint)
    return 0


def _prefs(setting: str, value: str | None) -> int:
    assert setting == "grill"
    if value is not None:
        if value not in ("page", "chat"):
            print(f"plan-review prefs grill: give page or chat, not '{value}'", file=sys.stderr)
            return 2
        mode: GrillMode = "page" if value == "page" else "chat"
        record(preferences_file(Path()), mode)
        return 0
    try:
        config, config_hint = _pipeline()
    except PipelineConfigError as error:
        print("\n".join(error.errors), file=sys.stderr)
        return 1
    source = preferences_source(Path())
    path = source.path
    try:
        prefs_file = load_preferences(path)
    except ValidationError as error:
        print("\n".join(named_errors(path, error)), file=sys.stderr)
        return 1
    chosen = grill_mode(config, prefs_file)
    _hint(config_hint)
    _hint(source.move_hint)
    if chosen is None:
        print(
            "no grill mode chosen: ask the owner, then `plan-review prefs grill <mode>`",
            file=sys.stderr,
        )
        return 3
    print(chosen)
    return 0


def _grill_schema() -> int:
    print(json.dumps(Turn.model_json_schema(), indent=2))
    return 0


def _grill_post(run_id: str, file: Path) -> int:
    if not file.is_file():
        print(f"{file.as_posix()}: file not found", file=sys.stderr)
        return 2
    work = ensure_work_dir(Path(), run_id)
    paths = RunPaths(work)
    store = GrillStore(paths.grill)
    drafts = GrillDraftStore(paths.grill_drafts)
    try:
        with drafts.held():
            state = store.post(Turn.parse(file.read_bytes()))
            # a draft must not outlive its question being open
            try:
                drafts.keep_only({q.id for q in state.open_questions()})
            except BrokenFile as error:
                print(error, file=sys.stderr)  # the turn is posted; the page reports this file
    except GrillError as error:
        print("\n".join(error.errors), file=sys.stderr)
        return 1
    print(f"posted: {len(state.rounds)} rounds, {len(state.open_questions())} questions open")
    return 0


def _grill_pending(run_id: str) -> int:
    store = GrillStore(RunPaths(_work_dir(run_id)).grill)
    try:
        state = store.get()
    except GrillError as error:
        print("\n".join(error.errors), file=sys.stderr)
        return 1
    result = {"confirmed": state.confirmed_at is not None, "pending": store.pending()}
    print(json.dumps(result, indent=2))
    return 0


def _grill_decisions(run_id: str) -> int:
    work = _work_dir(run_id)
    paths = RunPaths(work)
    try:
        state = GrillStore(paths.grill).get()
    except GrillError as error:
        print("\n".join(error.errors), file=sys.stderr)
        return 1
    if state.confirmed_at is None:
        print(f"the grill for {label(run_id)} is not confirmed yet", file=sys.stderr)
        return 1
    paths.decisions.write_text(decisions_markdown(state, label(run_id)), encoding="utf-8")
    print(paths.decisions.as_posix())
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
    problems = shape_problems(plan)
    if problems:
        print("\n".join(f"{file.as_posix()}: {line}" for line in problems), file=sys.stderr)
        return 1
    print(f"OK: plan for {label(plan.issue.id)} ({len(plan.element_ids())} elements)")
    return 0


def _serve(run_id: str, open_flag: str | None, *, detach: bool = False) -> int:
    hint = None
    try:
        if open_flag:
            open_mode = open_flag  # the flag wins, so a broken config doesn't matter
        else:
            config, hint = _pipeline()
            open_mode = config.viewer.open
    except PipelineConfigError as error:
        print("\n".join(error.errors), file=sys.stderr)
        return 1
    if not (STATIC_DIR / "index.html").is_file():
        print(
            f"{STATIC_DIR.as_posix()}: viewer page not built; run `npm --prefix web run build`",
            file=sys.stderr,
        )
        return 2
    plan_file = RunPaths(_work_dir(run_id)).plan
    page = ""  # the plan page is "/"; before there is a plan, the grill page is shown
    try:
        load_plan(plan_file)
    except PlanFileError as error:
        if not (error.missing and RunPaths(_work_dir(run_id)).grill.is_file()):
            print("\n".join(error.errors), file=sys.stderr)
            return 2 if error.missing else 1
        page = "grill"
    work = ensure_work_dir(Path(), run_id)  # the page writes comments and drafts there
    if detach:
        return _serve_detached(run_id, work, page, open_mode, hint)
    # Bind and listen before opening the browser: its first request then waits in the
    # socket's queue until uvicorn accepts it, instead of racing the server's startup.
    # Port 0 lets the OS pick a free port.
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen()
        url = f"http://127.0.0.1:{sock.getsockname()[1]}/{page}"
        print(f"plan-review: {label(run_id)} at {url} (Ctrl+C to stop)", flush=True)
        _hint(hint)  # after the URL line: /ship reads the first line of the output
        if open_mode == "browser":
            webbrowser.open(url)
        run_server(create_app(plan_file, STATIC_DIR), sock)
    return 0


def _serve_detached(run_id: str, work: Path, page: str, open_mode: str, hint: str | None) -> int:
    try:
        record, started = start_viewer(Path(), work, run_id)
    except ViewerFailed as error:
        print(error.log, file=sys.stderr, end="" if error.log.endswith("\n") else "\n")
        return error.code
    url = f"http://127.0.0.1:{record.port}/{page}"
    print(
        f"plan-review: {label(run_id)} at {url} (stop it with `plan-review stop {run_id}`)",
        flush=True,
    )
    _hint(hint)
    if started and open_mode == "browser":
        webbrowser.open(url)
    return 0


def _install(key: str) -> int:
    adapter = adapter_by_key(key)
    assert adapter is not None  # argparse limited the choices to the adapters
    return adapter.install()


def _stop(run_id: str) -> int:
    if stop_viewer(_work_dir(run_id), run_id):
        print(f"plan-review: stopped the viewer for {label(run_id)}")
    else:
        print(f"plan-review: no viewer is running for {label(run_id)}")
    return 0


def _viewer_process(args: argparse.Namespace) -> int:
    """The detached viewer itself: the server of `serve`, stoppable and stopping when idle."""
    run_id: str = args.run_id
    work = _work_dir(run_id)
    server: uvicorn.Server | None = None

    def request_stop() -> None:
        if server is not None:
            server.should_exit = True

    detached = DetachedViewer(
        run_id=run_id, token=args.token, request_stop=request_stop, record=record_file(work)
    )
    app = create_app(RunPaths(work).plan, STATIC_DIR, detached=detached)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", args.port))
        sock.listen()
        server = uvicorn.Server(uvicorn.Config(app, log_level="warning"))
        server.run(sockets=[sock])
    return 0


def _threads(run_id: str) -> int:
    open_threads = [
        t for t in ThreadStore(RunPaths(_work_dir(run_id)).comments).all() if not t.resolved
    ]
    print(json.dumps([t.model_dump(mode="json") for t in open_threads], indent=2))
    return 0


def _existing_work_dir(run_id: str) -> Path | None:
    """The run's folder; None (after saying so) if there is none, e.g. a wrong directory."""
    work = _work_dir(run_id)
    if work.is_dir():
        return work
    print(
        f"no {work.as_posix()}/ for {label(run_id)}: is this the project root?",
        file=sys.stderr,
    )
    return None


def _wait(run_id: str, timeout: str) -> int:
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
    work = _existing_work_dir(run_id)
    if work is None:
        return 1
    event = wait_for_event(EventLog(RunPaths(work).events), seconds)
    print(json.dumps(event, separators=(",", ":")), flush=True)
    return 0


def _status(run_id: str, text: str, *, done: bool, clear: bool) -> int:
    work = _existing_work_dir(run_id)
    if work is None:
        return 1
    if not clear and not text.strip():
        print("status text is empty", file=sys.stderr)  # before anything is moved aside
        return 1
    store = StatusStore(RunPaths(work).status)
    try:
        moved = store.set_aside()
        if moved:
            print(
                f"{store.path.as_posix()} was broken: moved to {moved.as_posix()}", file=sys.stderr
            )
        if clear:
            store.clear()
        else:
            store.set(text, done=done)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    if not clear:
        _confirm_delivered(work)
    return 0


def _confirm_delivered(work: Path) -> None:
    """A status says the agent has handled what `wait` last handed it."""
    try:
        EventLog(RunPaths(work).events).confirm()
    except BrokenFile as error:
        print("\n".join(error.errors), file=sys.stderr)  # the status is written all the same


def _reply(run_id: str, thread_id: str, text: str) -> int:
    try:
        ThreadStore(RunPaths(_work_dir(run_id)).comments).reply(thread_id, text, author="agent")
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
    plan_file = RunPaths(_work_dir(run_id)).plan
    try:
        plan = load_plan(plan_file)
        if plan.branch:  # already named (and maybe created): never name it again
            print(plan.branch)
            return 0
        config, hint = _pipeline()
        pattern = config.branch
    except (PlanFileError, PipelineConfigError) as error:
        print("\n".join(error.errors), file=sys.stderr)
        return 1
    branch = branch_name(run_id, plan.issue, pattern)
    record_branch(plan_file, branch)
    print(branch)
    _hint(hint)
    return 0


if __name__ == "__main__":  # the detached viewer starts as `python -m plan_review.cli`
    sys.exit(main())
