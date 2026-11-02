"""The `plan-review` command line."""

import argparse
import json
import sys
from importlib.metadata import version
from pathlib import Path

from pydantic import ValidationError

from plan_review.plan import Plan


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="plan-review")
    # Handled here rather than with action="version", which calls sys.exit():
    # main() returns its exit code so callers (and tests) stay in control.
    parser.add_argument("--version", action="store_true", help="print the version and exit")
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("schema", help="print the plan.json JSON Schema")
    validate = commands.add_parser("validate", help="check a plan.json file")
    validate.add_argument("file", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.version:
        print(f"plan-review {version('plan-review')}")
    elif args.command == "schema":
        print(json.dumps(Plan.model_json_schema(), indent=2))
    elif args.command == "validate":
        return _validate(args.file)
    return 0


def _validate(file: Path) -> int:
    if not file.is_file():
        print(f"{file}: file not found", file=sys.stderr)
        return 2
    try:
        plan = Plan.model_validate_json(file.read_text())
    except ValidationError as error:
        for line in _readable(error):
            print(line, file=sys.stderr)
        return 1
    print(f"OK: plan for #{plan.issue.number} ({len(plan.element_ids())} elements)")
    return 0


def _readable(error: ValidationError) -> list[str]:
    """One `location: message` line per error; plan-wide checks have no location."""
    lines: list[str] = []
    for e in error.errors():
        where = ".".join(str(part) for part in e["loc"])
        lines.append(f"{where}: {e['msg']}" if where else e["msg"])
    return lines
