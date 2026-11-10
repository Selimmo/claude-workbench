"""Writes each CLI's files from `workflow/`, or checks that the committed ones are fresh.

A maintainer tool, run as `uv run python -m plan_review.harness.generate [--check]`, so it stays
out of `plan-review --help`. Files are written and compared as bytes with LF endings, so
Windows agrees with everyone else.
"""

import argparse
import sys
from pathlib import Path

from plan_review.harness.adapters import ADAPTERS
from plan_review.harness.workflow import load_workflow

PACKAGE_ROOT = Path(__file__).parents[3]
COMMAND = "uv run python -m plan_review.harness.generate"


def expected_files(root: Path) -> dict[Path, bytes]:
    """Every generated file under `root`, with the bytes it should hold."""
    workflow = load_workflow(root / "workflow")
    return {
        root / path: text.encode("utf-8")
        for adapter in ADAPTERS
        for path, text in adapter.files(workflow).items()
    }


def _leftovers(root: Path, expected: dict[Path, bytes]) -> list[Path]:
    folders = {path.parent for path in expected}
    return sorted(
        path
        for folder in folders
        if folder.is_dir()
        for path in folder.iterdir()
        if path.is_file() and not path.name.startswith(".") and path not in expected
    )


def stale_files(root: Path) -> list[str]:
    """Generated files that are missing or different, and leftovers in generated folders."""
    expected = expected_files(root)
    stale = [
        path
        for path, content in expected.items()
        if not path.is_file() or path.read_bytes() != content
    ]
    return sorted(p.relative_to(root).as_posix() for p in [*stale, *_leftovers(root, expected)])


def write_files(root: Path) -> None:
    expected = expected_files(root)
    for path in _leftovers(root, expected):
        path.unlink()
    for path, content in expected.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m plan_review.harness.generate")
    parser.add_argument("--check", action="store_true", help="fail if a generated file is stale")
    parser.add_argument("--root", type=Path, default=PACKAGE_ROOT, help="the plugin folder")
    args = parser.parse_args(argv)
    if args.check:
        stale = stale_files(args.root)
        if stale:
            print("stale generated files (edit workflow/, not these):", file=sys.stderr)
            for name in stale:
                print(f"  {name}", file=sys.stderr)
            print(f"fix: {COMMAND}", file=sys.stderr)
            return 1
        return 0
    write_files(args.root)
    return 0


if __name__ == "__main__":
    sys.exit(main())
