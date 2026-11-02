"""The `plan-review` command line."""

import argparse
import json
import socket
import sys
import webbrowser
from importlib.metadata import version
from pathlib import Path

import uvicorn
from fastapi import FastAPI

from plan_review.plan import Plan, PlanFileError, load_plan
from plan_review.server import create_app

STATIC_DIR = Path(__file__).parent / "static"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="plan-review")
    # Handled here rather than with action="version", which calls sys.exit():
    # main() returns its exit code so callers (and tests) stay in control.
    parser.add_argument("--version", action="store_true", help="print the version and exit")
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("schema", help="print the plan.json JSON Schema")
    validate = commands.add_parser("validate", help="check a plan.json file")
    validate.add_argument("file", type=Path)
    serve = commands.add_parser("serve", help="open the viewer for an issue's plan")
    serve.add_argument("issue", type=int)
    serve.add_argument(
        "--open",
        choices=["browser", "none"],
        help="open the default browser, or only print the URL "
        "(default: viewer.open in .claude/pipeline.json, else browser)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.version:
        print(f"plan-review {version('plan-review')}")
    elif args.command == "schema":
        print(json.dumps(Plan.model_json_schema(), indent=2))
    elif args.command == "validate":
        return _validate(args.file)
    elif args.command == "serve":
        return _serve(args.issue, args.open or _configured_open())
    return 0


def _validate(file: Path) -> int:
    try:
        plan = load_plan(file)
    except PlanFileError as error:
        print("\n".join(error.errors), file=sys.stderr)
        return 2 if error.missing else 1
    print(f"OK: plan for #{plan.issue.number} ({len(plan.element_ids())} elements)")
    return 0


def _serve(issue: int, open_mode: str) -> int:
    if not (STATIC_DIR / "index.html").is_file():
        print(
            f"{STATIC_DIR}: viewer page not built; run `npm --prefix web run build`",
            file=sys.stderr,
        )
        return 2
    plan_file = Path(".claude", "work", str(issue), "plan.json")
    try:
        load_plan(plan_file)
    except PlanFileError as error:
        print("\n".join(error.errors), file=sys.stderr)
        return 2 if error.missing else 1
    # Bind and listen before opening the browser: its first request then waits in the
    # socket's queue until uvicorn accepts it, instead of racing the server's startup.
    # Port 0 lets the OS pick a free port.
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen()
        url = f"http://127.0.0.1:{sock.getsockname()[1]}/"
        print(f"plan-review: issue #{issue} at {url} (Ctrl+C to stop)", flush=True)
        if open_mode == "browser":
            webbrowser.open(url)
        run_server(create_app(plan_file, STATIC_DIR), sock)
    return 0


def _configured_open() -> str:
    config = Path(".claude", "pipeline.json")
    if not config.is_file():
        return "browser"
    return json.loads(config.read_text()).get("viewer", {}).get("open", "browser")


def run_server(app: FastAPI, sock: socket.socket) -> None:
    uvicorn.Server(uvicorn.Config(app, log_level="warning")).run(sockets=[sock])
