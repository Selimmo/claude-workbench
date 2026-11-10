"""The package root holds only __init__.py; every other module lives in a folder."""

import ast

from conftest import PLUGIN

ROOT = PLUGIN / "src" / "plan_review"


def test_the_package_root_holds_only_init() -> None:
    assert {path.name for path in ROOT.glob("*.py")} == {"__init__.py"}


def test_cli_is_a_folder() -> None:
    assert (ROOT / "cli").is_dir()
    assert not (ROOT / "cli.py").exists()


def test_the_command_line_has_one_file_per_command_group() -> None:
    files = {path.name for path in (ROOT / "cli").glob("*.py")}

    assert files == {
        f"{name}.py"
        for name in (
            "__init__",
            "__main__",
            "runtime",
            "viewer",
            "agent",
            "grill",
            "pipeline",
            "settings",
            "setup",
        )
    }


def test_cli_init_only_builds_the_parser_and_dispatches() -> None:
    tree = ast.parse((ROOT / "cli" / "__init__.py").read_text("utf-8"))

    top_level = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}

    assert top_level == {"main", "parser", "_usage"}


def test_only_approval_file_reaches_approved_json() -> None:
    # RunPaths.approved is the path of approved.json: only viewer/app.py (which hands it to
    # ApprovalFile, and still watches it) may name it.
    users = {
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("*.py")
        for node in ast.walk(ast.parse(path.read_text("utf-8")))
        if isinstance(node, ast.Attribute) and node.attr == "approved"
    }

    assert users == {"viewer/app.py"}


def test_events_holds_one_file_per_part() -> None:
    files = {path.stem for path in (ROOT / "events").glob("*.py")}

    assert files == {
        "__init__",
        "subscribers",
        "agent_events",
        "event_log",
        "last_event",
        "resend",
        "status",
        "waiter",
    }
    assert (ROOT / "review" / "approval_file.py").is_file()
