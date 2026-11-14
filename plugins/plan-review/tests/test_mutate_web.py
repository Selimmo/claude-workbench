"""scripts/mutate-web.sh: StrykerJS on only the web source files a branch touched."""

import os
import stat
import subprocess
from pathlib import Path

import pytest
from conftest import PLUGIN, git, posix_only

pytestmark = posix_only

SCRIPT = PLUGIN / "scripts" / "mutate-web.sh"


def write(root: Path, path: str, text: str = "x\n") -> None:
    (root / path).parent.mkdir(parents=True, exist_ok=True)
    (root / path).write_text(text)


@pytest.fixture
def plugin(tmp_path: Path) -> Path:
    """A plugin folder in a git repo whose `main` has two web sources and a test."""
    git(tmp_path, "init", "--quiet", "--initial-branch=main")
    git(tmp_path, "config", "user.email", "t@example.com")
    git(tmp_path, "config", "user.name", "t")
    for path in ("web/src/a.ts", "web/src/b.tsx", "web/src/a.test.ts", "web/src/gone.ts"):
        write(tmp_path, path)
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "--quiet", "-m", "main")
    git(tmp_path, "switch", "--quiet", "-c", "work")
    return tmp_path


def run(plugin: Path) -> tuple[subprocess.CompletedProcess[str], str | None]:
    """Run the script with a stand-in Stryker that records the arguments it got."""
    log = plugin / "stryker-args.txt"
    fake = plugin / "fake-stryker"
    fake.write_text(f'#!/bin/sh\necho "$PWD $*" > {log}\n')
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    result = subprocess.run(
        [SCRIPT],
        cwd=plugin,
        env={**os.environ, "STRYKER": str(fake)},
        capture_output=True,
        text=True,
        check=False,
    )
    return result, log.read_text().strip() if log.exists() else None


def test_mutates_the_web_sources_changed_since_main(plugin: Path) -> None:
    write(plugin, "web/src/a.ts", "committed change\n")
    git(plugin, "commit", "--quiet", "-am", "change a")
    write(plugin, "web/src/b.tsx", "uncommitted change\n")
    write(plugin, "web/src/new/c.ts")  # untracked: a reviewer sees work before it is committed

    result, args = run(plugin)

    assert result.returncode == 0, result.stderr
    assert args == f"{(plugin / 'web').resolve()} run --mutate src/a.ts,src/b.tsx,src/new/c.ts"


def test_leaves_out_tests_deleted_files_and_files_outside_web_src(plugin: Path) -> None:
    write(plugin, "web/src/a.ts", "change\n")
    write(plugin, "web/src/a.test.ts", "change\n")
    write(plugin, "web/src/test/setup.ts")
    write(plugin, "src/tool.py")
    write(plugin, "web/vite.config.ts", "change\n")
    (plugin / "web/src/gone.ts").unlink()

    _, args = run(plugin)

    assert args is not None and args.endswith("run --mutate src/a.ts")


def test_skips_stryker_when_no_web_source_changed(plugin: Path) -> None:
    write(plugin, "src/tool.py")
    write(plugin, "web/src/b.test.tsx")

    result, args = run(plugin)

    assert result.returncode == 0
    assert args is None
    assert "no web source changed since main" in result.stdout
