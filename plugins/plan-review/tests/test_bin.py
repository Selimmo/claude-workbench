"""bin/plan-review: what Claude Code puts on PATH for the agents and /ship."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import PACKAGE_VERSION

WRAPPER = Path(__file__).parents[1] / "bin" / "plan-review"


def run_launcher(launcher: Path, *args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run the launcher as the Bash tool does: directly on POSIX, through Git's sh on
    Windows, which cannot execute a shebang file itself. Not `bash`, which can be WSL's."""
    command = [str(launcher)]
    if sys.platform == "win32":
        sh = shutil.which("sh")
        assert sh, "Git for Windows' sh is not on PATH"
        command = [sh, launcher.as_posix()]  # forward slashes: the script runs dirname "$0"
    return subprocess.run([*command, *args], cwd=cwd, capture_output=True, text=True, check=False)


def site_packages(venv: Path) -> Path | None:
    """The virtualenv's site-packages: lib/python3.x/ on POSIX, Lib/ on Windows."""
    return next(
        iter([*venv.glob("lib/python*/site-packages"), *venv.glob("Lib/site-packages")]), None
    )


def test_runs_the_plugins_own_cli_from_any_directory(tmp_path: Path) -> None:
    result = run_launcher(WRAPPER, "--version", cwd=tmp_path)

    assert result.returncode == 0, result.stderr
    assert result.stdout == f"plan-review {PACKAGE_VERSION}\n"


def test_runs_by_name_from_path_like_the_bash_tool(tmp_path: Path) -> None:
    # Claude Code puts the plugin's bin/ on PATH; the shell finds the launcher by name.
    sh = shutil.which("sh")
    assert sh, "sh is not on PATH"
    env = {**os.environ, "PATH": os.pathsep.join([str(WRAPPER.parent), os.environ["PATH"]])}

    result = subprocess.run(
        [sh, "-c", "plan-review --version"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == f"plan-review {PACKAGE_VERSION}\n"


def test_keeps_the_callers_directory_as_the_project_root(tmp_path: Path) -> None:
    (tmp_path / ".plan-review").mkdir()
    (tmp_path / ".plan-review" / "config.json").write_text(json.dumps({"max_review_rounds": 5}))

    result = run_launcher(WRAPPER, "config", cwd=tmp_path)

    assert json.loads(result.stdout)["max_review_rounds"] == 5


@pytest.mark.timeout(120)  # a cold first run on Windows builds a whole virtualenv
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

    result = run_launcher(plugin / "bin" / "plan-review", "--version", cwd=tmp_path)

    assert result.returncode == 0, result.stderr
    packages = site_packages(plugin / ".venv")
    assert packages is not None, "the first run created no virtualenv"
    assert list(packages.glob("*plan_review*"))  # the package, or uv's editable .pth
    assert not (packages / "pytest").exists()


@pytest.mark.timeout(120)  # a cold first run builds a whole virtualenv
def test_an_installed_copy_finds_its_adapter(tmp_path: Path) -> None:
    # Laid out like the release zip: only the marker says it was installed through Claude Code.
    plugin = tmp_path / "plan-review"
    plugin.mkdir()
    for name in ["bin", "src", ".claude-plugin"]:
        shutil.copytree(
            WRAPPER.parents[1] / name, plugin / name, ignore=shutil.ignore_patterns("__pycache__")
        )
    for name in ["pyproject.toml", "uv.lock", "README.md", ".python-version"]:
        shutil.copy2(WRAPPER.parents[1] / name, plugin / name)
    log = tmp_path / "calls.log"
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    (fake_bin / "claude").write_text(f'#!/bin/sh\necho "$*" >> {log}\n')
    (fake_bin / "claude").chmod(0o755)
    if sys.platform == "win32":
        (fake_bin / "claude.cmd").write_text(f'@echo off\n>>"{log}" echo %*\n')
    path = os.pathsep.join([str(fake_bin), os.environ["PATH"]])

    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("PATH", path)
        result = run_launcher(plugin / "bin" / "plan-review", "upgrade", cwd=tmp_path)

    assert result.returncode == 0, result.stderr
    assert log.read_text().splitlines() == [
        "plugin marketplace update claude-workbench",
        "plugin update plan-review@claude-workbench",
    ]
