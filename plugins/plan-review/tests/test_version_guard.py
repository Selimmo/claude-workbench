"""scripts/version-guard.sh: CI fails when shipped plugin files change without a version bump.

Claude Code only fetches a plugin again when its version changes, so a change released
under an old version would never reach anyone who has that version installed.
"""

import subprocess
from pathlib import Path

import pytest
from conftest import VIEWER_BUILD_FILES, git, posix_only

pytestmark = posix_only


def guard(plugin: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["scripts/version-guard.sh"], cwd=plugin, capture_output=True, text=True, check=False
    )


def commit_change(plugin: Path, path: str) -> None:
    (plugin / path).write_text("v2\n")
    git(plugin, "commit", "--quiet", "-am", f"Change {path}")


def test_fails_when_a_shipped_file_changed_since_its_versions_release(repo: Path) -> None:
    commit_change(repo, "src/plan_review/cli/__init__.py")

    result = guard(repo)

    assert result.returncode == 1
    assert "src/plan_review/cli/__init__.py" in result.stderr
    assert "0.1.0" in result.stderr


def test_passes_once_the_version_is_bumped_past_the_release(repo: Path) -> None:
    commit_change(repo, "src/plan_review/cli/__init__.py")
    subprocess.run(["scripts/set-version.sh", "0.1.1"], cwd=repo, check=True)
    git(repo, "commit", "--quiet", "-am", "Bump")

    result = guard(repo)

    assert result.returncode == 0, result.stderr


def test_ignores_files_that_do_not_ship(repo: Path) -> None:
    commit_change(repo, "tests/test_x.py")

    result = guard(repo)

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("source", ["web/src/App.tsx", *VIEWER_BUILD_FILES])
def test_fails_when_the_viewer_pages_source_changed(repo: Path, source: str) -> None:
    # static/ is gitignored, but the zip ships the page built from web/.
    commit_change(repo, source)

    result = guard(repo)

    assert result.returncode == 1
    assert source in result.stderr


def test_ignores_the_viewer_pages_tests(repo: Path) -> None:
    commit_change(repo, "web/src/App.test.tsx")

    result = guard(repo)

    assert result.returncode == 0, result.stderr


def test_fails_when_the_shipped_license_changed(repo: Path) -> None:
    (repo.parents[1] / "LICENSE").write_text("MIT, changed\n")
    git(repo, "commit", "--quiet", "-am", "License")

    result = guard(repo)

    assert result.returncode == 1
    assert "LICENSE" in result.stderr
