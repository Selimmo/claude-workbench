"""The package root holds only __init__.py; every other module lives in a folder."""

from conftest import PLUGIN

ROOT = PLUGIN / "src" / "plan_review"


def test_the_package_root_holds_only_init() -> None:
    assert {path.name for path in ROOT.glob("*.py")} == {"__init__.py"}
