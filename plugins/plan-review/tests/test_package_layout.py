"""The package root holds only the entry points; every other module lives in a folder."""

from conftest import PLUGIN

ROOT = PLUGIN / "src" / "plan_review"


def test_the_package_root_holds_only_init_and_cli() -> None:
    assert {path.name for path in ROOT.glob("*.py")} == {"__init__.py", "cli.py"}
