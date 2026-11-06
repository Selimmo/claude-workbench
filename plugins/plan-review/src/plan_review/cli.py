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
from pydantic import ValidationError

from plan_review.decisions_md import decisions_markdown
from plan_review.file_errors import BrokenFile, named_errors
from plan_review.grill import GrillError, GrillStore
from plan_review.grill_drafts import GrillDraftStore
from plan_review.grill_turn import Turn
from plan_review.orchestration import MalformedReview, branch_name, tree_hash, verdict
from plan_review.pipeline import PipelineConfigError, load_pipeline
from plan_review.plan import Plan, PlanFileError, load_plan, record_branch
from plan_review.prefs import GrillMode, grill_mode, load_preferences, record
from plan_review.run_id import InvalidRunId, check_run_id, label
from plan_review.server import create_app
from plan_review.status import StatusStore
from plan_review.threads import BlankComment, ThreadNotFound, ThreadStore
from plan_review.upgrade import upgrade
from plan_review.workdir import (
    ensure_work_dir,
    new_prompt_work_dir,
    preferences_file,
    preferences_path,
    work_dir,
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


PIPELINE_FILE = Path(".claude", "pipeline.json")


def _usage(parser: argparse.ArgumentParser) -> int:
    parser.print_help(sys.stderr)
    return 2


def _config() -> int:
    try:
        config = load_pipeline(PIPELINE_FILE)
    except PipelineConfigError as error:
        print("\n".join(error.errors), file=sys.stderr)
        return 1
    print(config.model_dump_json(indent=2))
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
        config = load_pipeline(PIPELINE_FILE)
    except PipelineConfigError as error:
        print("\n".join(error.errors), file=sys.stderr)
        return 1
    path = preferences_path(Path())
    try:
        prefs_file = load_preferences(path)
    except ValidationError as error:
        print("\n".join(named_errors(path, error)), file=sys.stderr)
        return 1
    chosen = grill_mode(config, prefs_file)
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
    store = GrillStore(work / "grill.json")
    drafts = GrillDraftStore(work / "grill_drafts.json")
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
    store = GrillStore(_work_dir(run_id) / "grill.json")
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
    try:
        state = GrillStore(work / "grill.json").get()
    except GrillError as error:
        print("\n".join(error.errors), file=sys.stderr)
        return 1
    if state.confirmed_at is None:
        print(f"the grill for {label(run_id)} is not confirmed yet", file=sys.stderr)
        return 1
    (work / "decisions.md").write_text(decisions_markdown(state, label(run_id)), encoding="utf-8")
    print((work / "decisions.md").as_posix())
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
    page = ""  # the plan page is "/"; before there is a plan, the grill page is shown
    try:
        load_plan(plan_file)
    except PlanFileError as error:
        if not (error.missing and (_work_dir(run_id) / "grill.json").is_file()):
            print("\n".join(error.errors), file=sys.stderr)
            return 2 if error.missing else 1
        page = "grill"
    ensure_work_dir(Path(), run_id)  # the page writes comments and drafts there
    # Bind and listen before opening the browser: its first request then waits in the
    # socket's queue until uvicorn accepts it, instead of racing the server's startup.
    # Port 0 lets the OS pick a free port.
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen()
        url = f"http://127.0.0.1:{sock.getsockname()[1]}/{page}"
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
    if not clear and not text.strip():
        print("status text is empty", file=sys.stderr)  # before anything is moved aside
        return 1
    store = StatusStore(work / "status.json")
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
