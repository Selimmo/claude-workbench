"""The `plan-review` command line.

The parser lives here, so the commands are registered (and listed in `--help`) in one order.
Each command's function is in the file of its group."""

import argparse
import sys
from collections.abc import Callable
from importlib.metadata import version
from pathlib import Path

from plan_review.cli import agent, pipeline, settings, setup, viewer
from plan_review.cli import grill as grill_commands
from plan_review.cli.runtime import Runtime
from plan_review.harness.adapters import all_adapters
from plan_review.paths.run_id import InvalidRunId, check_run_id
from plan_review.utils.json_files import BrokenFile

Run = Callable[[argparse.Namespace, Runtime], int]


def parser() -> argparse.ArgumentParser:
    top = argparse.ArgumentParser(prog="plan-review")
    # Handled here rather than with action="version", which calls sys.exit():
    # main() returns its exit code so callers (and tests) stay in control.
    top.add_argument("--version", action="store_true", help="print the version and exit")
    commands = top.add_subparsers(dest="command", metavar="command")

    def command(name: str, help: str | None, run: Run) -> argparse.ArgumentParser:
        # No `help=` at all hides a subcommand from the listing; `help=None` would not.
        sub = commands.add_parser(name) if help is None else commands.add_parser(name, help=help)
        sub.set_defaults(run=run)
        return sub

    tool_keys = [h.key for h in all_adapters()]
    command("schema", "print the plan.json JSON Schema", lambda a, rt: pipeline.schema())
    init = command(
        "init",
        "create a run's .plan-review/work/<id>/ folder (or --prompt <name>: <name>-<date>)",
        lambda a, rt: pipeline.init(a.run_id, a.prompt, runtime=rt),
    )
    init.add_argument("run_id", nargs="?", help="an issue number or key, e.g. 42 or PROJ-123")
    init.add_argument("--prompt", metavar="NAME", help="start a prompt run named NAME-<today>")
    command(
        "validate", "check a plan.json file", lambda a, rt: pipeline.validate(a.file)
    ).add_argument("file", type=Path)
    serve = command(
        "serve",
        "open the viewer for a run's plan",
        lambda a, rt: viewer.serve(a.run_id, a.open, detach=a.detach, runtime=rt),
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
        lambda a, rt: setup.install(a.cli),
    )
    install.add_argument("cli", choices=[a.key for a in all_adapters()])
    command(
        "stop", "stop a run's detached viewer", lambda a, rt: viewer.stop(a.run_id, runtime=rt)
    ).add_argument("run_id")
    process = command(
        "viewer-process",
        None,
        lambda a, rt: viewer.viewer_process(a.run_id, a.port, a.token, runtime=rt),
    )
    process.add_argument("run_id")
    process.add_argument("--port", type=int, required=True)
    process.add_argument("--token", required=True)
    config = command(
        "config",
        "print the settings in force and where each came from; check them",
        lambda a, rt: settings.config(a.harness),
    )
    config.add_argument("--harness", choices=tool_keys, help="only this tool's section")
    launch = command(
        "launch",
        "how to start one agent: its name, model and effort, from the config",
        lambda a, rt: settings.launch(a.name, a.harness),
    )
    launch.add_argument("name")
    launch.add_argument("--harness", choices=tool_keys, required=True)
    command(
        "threads",
        "list a run's open comment threads as JSON",
        lambda a, rt: agent.threads(a.run_id, runtime=rt),
    ).add_argument("run_id")
    reply = command(
        "reply",
        "answer a comment thread as the agent",
        lambda a, rt: agent.reply(a.run_id, a.thread_id, a.text, runtime=rt),
    )
    reply.add_argument("run_id")
    reply.add_argument("thread_id")
    reply.add_argument("text")
    status = command(
        "status",
        "show the owner what the agent is doing with their review (latest text wins)",
        lambda a, rt: agent.status(a.run_id, a.text, done=a.done, clear=a.clear, runtime=rt),
    )
    status.add_argument("run_id")
    status.add_argument("text", nargs="?", default="")
    status.add_argument("--done", action="store_true", help="mark it finished")
    status.add_argument("--clear", action="store_true", help="remove the status line")
    wait = command(
        "wait",
        'the next thing the owner did, as one JSON line; {"type":"timeout"} if nothing',
        lambda a, rt: agent.wait(a.run_id, a.timeout, runtime=rt),
    )
    wait.add_argument("run_id")
    wait.add_argument(
        "--timeout", default="240", metavar="SECONDS", help="how long to wait (default: 240)"
    )
    command(
        "branch",
        "the branch name for a run: recorded in its plan, else made",
        lambda a, rt: pipeline.branch(a.run_id, runtime=rt),
    ).add_argument("run_id")
    command(
        "verdict",
        "a review's verdict: exit 0 PASS, 1 FINDINGS, 2 malformed",
        lambda a, rt: pipeline.verdict(a.file),
    ).add_argument("file", type=Path)
    grill = command(
        "grill", "the page grill: post turns, see what is pending", lambda a, rt: _usage(grill)
    )
    grill_subcommands = grill.add_subparsers(dest="grill_command")

    def grill_command(name: str, help: str, run: Run) -> argparse.ArgumentParser:
        sub = grill_subcommands.add_parser(name, help=help)
        sub.set_defaults(run=run)
        return sub

    post = grill_command(
        "post",
        "add the agent's next turn to a run's grill.json",
        lambda a, rt: grill_commands.post(a.run_id, a.file, runtime=rt),
    )
    post.add_argument("run_id")
    post.add_argument("file", type=Path, help="the turn, as JSON (see `grill schema`)")
    pending = grill_command(
        "pending",
        "whether the owner confirmed, and what they did that is not answered yet (JSON)",
        lambda a, rt: grill_commands.pending(a.run_id, runtime=rt),
    )
    pending.add_argument("run_id")
    decisions = grill_command(
        "decisions",
        "write W/decisions.md from the confirmed grill",
        lambda a, rt: grill_commands.decisions(a.run_id, runtime=rt),
    )
    decisions.add_argument("run_id")
    grill_command(
        "schema", "print the JSON Schema of a turn", lambda a, rt: grill_commands.schema()
    )
    answer = grill_command(
        "answer",
        "record the owner's chat answers (a JSON list) in a run's grill.json",
        lambda a, rt: grill_commands.answer(a.run_id, a.file, runtime=rt),
    )
    answer.add_argument("run_id")
    answer.add_argument("file", type=Path, help="the answers, as a JSON list")
    confirm = grill_command(
        "confirm",
        "record that the owner confirmed the shared understanding",
        lambda a, rt: grill_commands.confirm(a.run_id, runtime=rt),
    )
    confirm.add_argument("run_id")
    reopen = grill_command(
        "reopen",
        "record that the owner said 'not yet', and what is missing",
        lambda a, rt: grill_commands.reopen(a.run_id, a.text, runtime=rt),
    )
    reopen.add_argument("run_id")
    reopen.add_argument("text")
    prefs = command(
        "prefs",
        "the owner's recorded choices: `prefs grill [page|chat]` sets or prints the grill mode",
        lambda a, rt: settings.prefs(a.setting, a.value, a.project),
    )
    prefs.add_argument("setting", choices=["grill"])
    prefs.add_argument("value", nargs="?", help="page or chat; leave out to print the mode")
    prefs.add_argument(
        "--project", action="store_true", help="save in this project's config.json, not yours"
    )
    command(
        "upgrade",
        "update the installed plugin to its newest release",
        lambda a, rt: setup.upgrade(),
    )
    command(
        "tree-hash", "fingerprint of uncommitted changes (git)", lambda a, rt: pipeline.tree_hash()
    )
    return top


def _usage(parser: argparse.ArgumentParser) -> int:
    parser.print_help(sys.stderr)
    return 2


def main(argv: list[str] | None = None, *, runtime: Runtime | None = None) -> int:
    args = parser().parse_args(argv)
    if args.version:
        print(f"plan-review {version('plan-review')}")
        return 0
    run: Run | None = getattr(args, "run", None)
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
        return run(args, Runtime() if runtime is None else runtime)
    except BrokenFile as error:
        print("\n".join(error.errors), file=sys.stderr)
        return 1
