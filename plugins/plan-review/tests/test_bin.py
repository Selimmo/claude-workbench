"""bin/plan-review: what Claude Code puts on PATH for the agents and /ship."""

import json
import shutil
import subprocess
from pathlib import Path

from conftest import PACKAGE_VERSION

WRAPPER = Path(__file__).parents[1] / "bin" / "plan-review"


def test_runs_the_plugins_own_cli_from_any_directory(tmp_path: Path) -> None:
    result = subprocess.run(
        [str(WRAPPER), "--version"], cwd=tmp_path, capture_output=True, text=True, check=False
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == f"plan-review {PACKAGE_VERSION}\n"


def test_keeps_the_callers_directory_as_the_project_root(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "pipeline.json").write_text(json.dumps({"max_review_rounds": 5}))

    result = subprocess.run(
        [str(WRAPPER), "config"], cwd=tmp_path, capture_output=True, text=True, check=False
    )

    assert json.loads(result.stdout)["max_review_rounds"] == 5


def test_an_installed_copy_gets_only_the_clis_own_dependencies(tmp_path: Path) -> None:
    # Installed from a release zip, its first run creates the environment: no dev tools.
    plugin = tmp_path / "plan-review"
    plugin.mkdir()
    for name in ["bin", "src"]:
        shutil.copytree(
            WRAPPER.parents[1] / name, plugin / name, ignore=shutil.ignore_patterns("__pycache__")
        )
    for name in ["pyproject.toml", "uv.lock", "README.md", ".python-version"]:
        shutil.copy2(WRAPPER.parents[1] / name, plugin / name)

    result = subprocess.run(
        [str(plugin / "bin" / "plan-review"), "--version"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert not list((plugin / ".venv").glob("lib/python*/site-packages/pytest"))
