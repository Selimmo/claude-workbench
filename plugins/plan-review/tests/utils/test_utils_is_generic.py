"""utils/ holds generic helpers: it imports nothing else from plan_review."""

import ast

from conftest import PLUGIN

UTILS = PLUGIN / "src" / "plan_review" / "utils"


def outside_imports(source: str, depth: int = 0) -> list[str]:
    """Imports of other plan_review folders; depth = folders below utils/ the file sits in."""
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level > depth + 1:
            names = ["." * node.level + (node.module or "")]  # climbs above utils/
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names = [node.module]
        else:
            continue
        found += [
            name
            for name in names
            if name.startswith(".")
            or (
                (name == "plan_review" or name.startswith("plan_review."))
                and name != "plan_review.utils"
                and not name.startswith("plan_review.utils.")
            )
        ]
    return found


def test_utils_imports_nothing_else_from_the_package() -> None:
    modules = sorted(UTILS.rglob("*.py"))

    found = {
        path.relative_to(UTILS).as_posix(): names
        for path in modules
        if (
            names := outside_imports(
                path.read_text(encoding="utf-8"), len(path.relative_to(UTILS).parts) - 1
            )
        )
    }

    assert modules
    assert found == {}


def test_outside_imports_flags_relative_imports_that_leave_utils() -> None:
    assert outside_imports("from ..review import threads") == ["..review"]
    assert outside_imports("from .. import review") == [".."]
    assert outside_imports("from . import text\nfrom .json_files import read") == []
    assert outside_imports("from ..review import x", depth=1) == []


def test_outside_imports_flags_absolute_imports_of_other_folders() -> None:
    assert outside_imports("from plan_review.review import threads") == ["plan_review.review"]
    assert outside_imports("import plan_review") == ["plan_review"]
    assert outside_imports("from plan_review.utils import text") == []
