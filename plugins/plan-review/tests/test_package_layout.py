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


def _defined(
    path: str, *kinds: type[ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef]
) -> set[str]:
    """The names of the top-level functions and classes a viewer/ file defines."""
    tree = ast.parse((ROOT / "viewer" / path).read_text("utf-8"))
    return {node.name for node in tree.body if isinstance(node, kinds)}


def test_create_apps_parts_live_in_their_own_files() -> None:
    assert _defined("app.py", ast.FunctionDef, ast.AsyncFunctionDef) == {
        "create_app",
        "_listen",
    }
    assert "FileWatcher" in _defined("file_watcher.py", ast.ClassDef)
    assert "add_error_handlers" in _defined("error_handlers.py", ast.FunctionDef)
    assert "serve_page" in _defined("page_routes.py", ast.FunctionDef)


def test_create_app_knows_nothing_of_detached_mode() -> None:
    tree = ast.parse((ROOT / "viewer" / "app.py").read_text("utf-8"))

    imported = {
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module
    }
    (create_app,) = (
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "create_app"
    )
    parameters = {arg.arg for arg in create_app.args.args + create_app.args.kwonlyargs}

    detached_modules = {
        f"plan_review.viewer.{name}"
        for name in ("detach", "lifetime", "launcher", "record", "client")
    }
    assert imported & detached_modules == set()
    assert "detached" not in parameters


def test_the_viewer_folder_holds_one_file_per_part() -> None:
    files = {path.stem for path in (ROOT / "viewer").glob("*.py")}

    assert files == {
        "__init__",
        "app",
        "file_watcher",
        "error_handlers",
        "page_routes",
        "start_page",
        "lifetime",
        "record",
        "launcher",
        "client",
    }


def test_only_viewer_record_reaches_viewer_json() -> None:
    # RunPaths.viewer is the path of viewer.json: only viewer/record.py may name it. The
    # pipeline config's `config.viewer` is another thing, and is left out.
    users = {
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("*.py")
        for node in ast.walk(ast.parse(path.read_text("utf-8")))
        if isinstance(node, ast.Attribute)
        and node.attr == "viewer"
        and not (isinstance(node.value, ast.Name) and node.value.id == "config")
    }

    assert users == {"viewer/record.py"}


def test_only_the_runtime_starts_uvicorn() -> None:
    users = {
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("*.py")
        for node in ast.walk(ast.parse(path.read_text("utf-8")))
        if (isinstance(node, ast.Import) and any(a.name == "uvicorn" for a in node.names))
        or (isinstance(node, ast.ImportFrom) and node.module == "uvicorn")
    }

    assert users == {"cli/runtime.py"}
