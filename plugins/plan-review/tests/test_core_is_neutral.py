"""The core and the page name no CLI: everything about one lives in an adapter."""

import re
import subprocess

from conftest import PLUGIN

SRC = PLUGIN / "src" / "plan_review"
CLI_NAMES = re.compile(r"claude|codex", re.IGNORECASE)
MONITOR = re.compile(r"\bMonitor\b")  # Claude Code's tool: exact case, so "monitoring" is fine

# Files that must name the old files and author value (migration.py) or the repo (releases.py).
PYTHON_EXCEPTIONS = {"migration.py", "releases.py"}
PAGE_EXCEPTIONS = {"web/src/threads.ts": "export type Author = 'owner' | 'agent' | 'claude'"}


def mentions(text: str) -> list[str]:
    return [
        line.strip() for line in text.splitlines() if CLI_NAMES.search(line) or MONITOR.search(line)
    ]


def test_the_core_names_no_cli() -> None:
    found = {
        path.relative_to(SRC).as_posix(): lines
        for path in sorted(SRC.rglob("*.py"))
        if "adapters" not in path.relative_to(SRC).parts
        and path.name not in PYTHON_EXCEPTIONS
        and "static" not in path.relative_to(SRC).parts
        and (lines := mentions(path.read_text(encoding="utf-8")))
    }

    assert found == {}


def tracked_page_files() -> list[str]:
    listed = subprocess.run(
        ["git", "ls-files", "web/src"], cwd=PLUGIN, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    return [
        name
        for name in listed
        if re.search(r"\.(ts|tsx|css)$", name) and not re.search(r"\.test\.|/test/", name)
    ]


def test_the_page_names_no_cli() -> None:
    found: dict[str, list[str]] = {}
    for name in tracked_page_files():
        lines = mentions((PLUGIN / name).read_text(encoding="utf-8"))
        allowed = PAGE_EXCEPTIONS.get(name)
        lines = [line for line in lines if allowed is None or allowed not in line]
        if lines:
            found[name] = lines

    assert found == {}


def test_the_workflow_source_names_no_cli() -> None:
    forbidden = re.compile(
        r"claude|codex|Monitor|run_in_background|\$ARGUMENTS|Skill tool|Bash tool"
        r"|\bopus\b|\bsonnet\b|\bhaiku\b",
        re.IGNORECASE,
    )
    found = {
        path.relative_to(PLUGIN).as_posix(): [
            line.strip() for line in path.read_text().splitlines() if forbidden.search(line)
        ]
        for path in sorted((PLUGIN / "workflow").rglob("*.md"))
    }

    assert {name: lines for name, lines in found.items() if lines} == {}
