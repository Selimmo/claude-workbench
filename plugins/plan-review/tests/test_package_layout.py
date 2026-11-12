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


def _grill_tree(name: str) -> ast.Module:
    return ast.parse((ROOT / "grill" / name).read_text("utf-8"))


def _iterated_attributes(node: ast.AST) -> set[str]:
    """The attribute names a `for` or a comprehension loops over, anywhere under node."""
    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.For | ast.comprehension) and isinstance(child.iter, ast.Attribute):
            names.add(child.iter.attr)
    return names


def test_only_grill_state_walks_the_rounds() -> None:
    walkers: set[str] = set()
    for path in sorted((ROOT / "grill").glob("*.py")):
        tree = ast.parse(path.read_text("utf-8"))
        for node in tree.body:
            inside_state = isinstance(node, ast.ClassDef) and node.name == "GrillState"
            if not inside_state and "rounds" in _iterated_attributes(node):
                walkers.add(path.name)

    assert walkers == set()


def test_turn_apply_stays_one_method_with_a_helper_per_loop() -> None:
    (turn,) = (
        node
        for node in _grill_tree("turn.py").body
        if isinstance(node, ast.ClassDef) and node.name == "Turn"
    )
    methods = [node for node in turn.body if isinstance(node, ast.FunctionDef)]
    (apply,) = (m for m in methods if m.name == "apply")
    in_apply = list(ast.walk(apply))

    assert "_round_problems" in {m.name for m in methods}
    assert not [n for n in in_apply if isinstance(n, ast.For | ast.DictComp)]


def _top_level(folder: str, name: str) -> set[str]:
    tree = ast.parse((ROOT / folder / name).read_text("utf-8"))
    return {
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
    }


def test_the_plan_folder_holds_one_file_per_part() -> None:
    files = {path.stem for path in (ROOT / "plan").glob("*.py")}

    assert files == {"__init__", "model", "plan_file", "diagram_checks"}
    assert "Plan" in _top_level("plan", "model.py")
    assert {"load_plan", "record_branch", "PlanFileError"} <= _top_level("plan", "plan_file.py")
    assert "shape_problems" in _top_level("plan", "diagram_checks.py")


def _imported_modules(tree: ast.AST, package: str = "plan_review.grill") -> set[str]:
    """Every module a file imports; a relative import counts as coming from `package`."""
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = package if node.level else (node.module or "")
            if node.level and node.module:
                base = f"{package}.{node.module}"
            found.add(base)
            found.update(f"{base}.{alias.name}" for alias in node.names)
    return found


def test_grill_state_imports_nothing_else_from_grill() -> None:
    state = {
        m
        for m in _imported_modules(_grill_tree("state.py"))
        if m == "plan_review.grill" or m.startswith("plan_review.grill.")
    }
    assert state == set()

    for path in sorted((ROOT / "grill").glob("*.py")):
        tree = ast.parse(path.read_text("utf-8"))
        assert "TYPE_CHECKING" not in {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}, (
            path
        )
        for fn in (
            n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
        ):
            local = [n for n in ast.walk(fn) if isinstance(n, ast.Import | ast.ImportFrom)]
            assert local == [], path


def test_the_grill_folder_holds_one_file_per_part() -> None:
    files = {path.stem for path in (ROOT / "grill").glob("*.py")}

    assert files == {
        "__init__",
        "state",
        "store",
        "owner_rules",
        "pending_text",
        "turn",
        "drafts",
        "routes",
        "decisions_md",
    }


def _grill_sources() -> dict[str, str]:
    return {p.name: p.read_text("utf-8") for p in (ROOT / "grill").glob("*.py")}


def _builds_grill_error_in(tree: ast.AST) -> bool:
    return any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "GrillError"
        for n in ast.walk(tree)
    )


def test_every_owner_rule_lives_in_owner_rules() -> None:
    assert not _builds_grill_error_in(_grill_tree("routes.py"))
    body = _grill_tree("store.py").body
    builders = {getattr(n, "name", "") for n in body if _builds_grill_error_in(n)}
    assert builders == {"load_grill"}
    for name in ("routes.py", "store.py"):
        assert "plan_review.grill.owner_rules" in _imported_modules(_grill_tree(name))
    sources = _grill_sources().values()
    for message in (
        "the owner already confirmed the grill",
        "The agent has not said the grill is done yet",
    ):
        assert sum(src.count(message) for src in sources) == 1, message


def test_the_grill_lock_order_is_written_once() -> None:
    held_in: dict[str, set[str]] = {}
    for path in sorted((ROOT / "grill").glob("*.py")):
        if path.name == "drafts.py":
            continue
        for fn in ast.walk(ast.parse(path.read_text("utf-8"))):
            if not isinstance(fn, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            for call in ast.walk(fn):
                if isinstance(call, ast.Attribute) and call.attr == "held":
                    held_in.setdefault(path.name, set()).add(fn.name)

    assert held_in == {"store.py": {"drafts_then_grill"}}
    assert "drafts_then_grill" in {
        n.id for n in ast.walk(_grill_tree("routes.py")) if isinstance(n, ast.Name)
    }
