"""release.sh: set the version, tag and push, in one command."""

import json
import subprocess
from pathlib import Path

import pytest
from conftest import TAG, git, posix_only

pytestmark = posix_only


def release(plugin: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["./release.sh", *args], cwd=plugin, capture_output=True, text=True, check=False
    )


def released_version(plugin: Path) -> str:
    """plugin.json's version on origin's main."""
    text = git(plugin, "show", "origin/main:plugins/plan-review/.claude-plugin/plugin.json")
    return json.loads(text)["version"]


def test_patch_bumps_the_last_released_version(repo: Path) -> None:
    result = release(repo, "patch")

    assert result.returncode == 0, result.stderr
    git(repo, "fetch", "--quiet", "origin")
    assert released_version(repo) == "0.1.1"


def test_tags_the_release_commit_and_pushes_the_tag(repo: Path) -> None:
    release(repo, "patch")

    origin_tag = git(repo, "ls-remote", "--tags", "origin", TAG.format("0.1.1") + "^{}")
    git(repo, "fetch", "--quiet", "origin")
    assert origin_tag, "the tag is not on origin"
    assert origin_tag.split()[0] == git(repo, "rev-parse", "origin/main")


def test_an_explicit_version_is_released_as_given(repo: Path) -> None:
    result = release(repo, "0.3.0")

    assert result.returncode == 0, result.stderr
    git(repo, "fetch", "--quiet", "origin")
    assert released_version(repo) == "0.3.0"


def test_a_version_already_set_on_main_is_tagged_without_a_new_commit(repo: Path) -> None:
    # A pull request bumped it already (the version guard asks for that).
    subprocess.run(["scripts/set-version.sh", "0.1.1"], cwd=repo, check=True)
    git(repo, "commit", "--quiet", "-am", "Bump")
    git(repo, "push", "--quiet", "origin", "main")
    bumped = git(repo, "rev-parse", "HEAD")

    result = release(repo, "patch")

    assert result.returncode == 0, result.stderr
    git(repo, "fetch", "--quiet", "origin")
    assert git(repo, "rev-parse", "origin/main") == bumped
    assert git(repo, "rev-parse", TAG.format("0.1.1") + "^{}") == bumped


def test_without_any_release_yet_patch_bumps_the_current_version(repo: Path) -> None:
    git(repo, "tag", "-d", TAG.format("0.1.0"))
    git(repo, "push", "--quiet", "origin", ":" + TAG.format("0.1.0"))

    result = release(repo, "patch")

    assert result.returncode == 0, result.stderr
    git(repo, "fetch", "--quiet", "origin")
    assert released_version(repo) == "0.1.1"


def origin_state(plugin: Path) -> str:
    return git(plugin, "ls-remote", "origin")


def test_refuses_uncommitted_changes_and_pushes_nothing(repo: Path) -> None:
    before = origin_state(repo)
    (repo / "README.md").write_text("edited\n")

    result = release(repo, "patch")

    assert result.returncode == 1
    assert "uncommitted changes" in result.stderr
    assert origin_state(repo) == before


def test_refuses_to_release_off_main(repo: Path) -> None:
    before = origin_state(repo)
    git(repo, "switch", "--quiet", "-c", "34-feature")

    result = release(repo, "patch")

    assert result.returncode == 1
    assert "main" in result.stderr
    assert origin_state(repo) == before


def test_refuses_a_version_not_newer_than_the_last_release(repo: Path) -> None:
    before = origin_state(repo)

    result = release(repo, "0.1.0")

    assert result.returncode == 1
    assert "not newer than 0.1.0" in result.stderr
    assert origin_state(repo) == before


@pytest.mark.parametrize("args", [(), ("minor",), ("1.2",), ("v1.2.3",), ("1.2.3x",), ("1.2.3.4",)])
def test_refuses_anything_but_a_version_or_patch_with_its_usage(
    repo: Path, args: tuple[str, ...]
) -> None:
    result = release(repo, *args)

    assert result.returncode == 2
    assert "usage: ./release.sh <version|patch>" in result.stderr


def test_the_python_package_gets_the_same_version(repo: Path) -> None:
    # `plan-review --version` reads it, and CI's `uv sync --locked` needs uv.lock to match.
    release(repo, "patch")

    pyproject = git(repo, "show", "origin/main:plugins/plan-review/pyproject.toml")
    lock = git(repo, "show", "origin/main:plugins/plan-review/uv.lock")
    assert 'version = "0.1.1"' in pyproject
    assert 'name = "plan-review"\nversion = "0.1.1"' in lock


def test_patch_releases_a_bigger_bump_already_set_on_main(repo: Path) -> None:
    # A pull request set 0.2.0 for a new feature: `patch` must not take it back to 0.1.1.
    subprocess.run(["scripts/set-version.sh", "0.2.0"], cwd=repo, check=True)
    git(repo, "commit", "--quiet", "-am", "Bump")
    git(repo, "push", "--quiet", "origin", "main")
    bumped = git(repo, "rev-parse", "HEAD")

    result = release(repo, "patch")

    assert result.returncode == 0, result.stderr
    git(repo, "fetch", "--quiet", "origin")
    assert released_version(repo) == "0.2.0"
    assert git(repo, "rev-parse", TAG.format("0.2.0") + "^{}") == bumped


def test_refuses_when_origin_main_moved_on_since_the_last_pull(repo: Path, tmp_path: Path) -> None:
    other = tmp_path / "other"
    git(tmp_path, "clone", "--quiet", git(repo, "remote", "get-url", "origin"), str(other))
    (other / "notes.md").write_text("someone else's change\n")
    git(other, "add", "notes.md")
    git(other, "commit", "--quiet", "-m", "Elsewhere")
    git(other, "push", "--quiet", "origin", "main")
    before = origin_state(repo)

    result = release(repo, "patch")

    assert result.returncode == 1
    assert "origin/main" in result.stderr
    assert origin_state(repo) == before


@pytest.mark.parametrize(
    ("tags", "expected"), [(["0.1.9"], "0.1.10"), (["0.1.9", "0.1.10"], "0.1.11")]
)
def test_patch_follows_version_order_not_text_order(
    repo: Path, tags: list[str], expected: str
) -> None:
    for version in tags:
        git(repo, "tag", "-a", TAG.format(version), "-m", version)
    git(repo, "push", "--quiet", "origin", "--tags")

    result = release(repo, "patch")

    assert result.returncode == 0, result.stderr
    git(repo, "fetch", "--quiet", "origin")
    assert released_version(repo) == expected


def test_without_any_release_yet_refuses_the_version_already_in_plugin_json(repo: Path) -> None:
    # Claude Code may have that version cached already, and would never fetch it again.
    git(repo, "tag", "-d", TAG.format("0.1.0"))
    git(repo, "push", "--quiet", "origin", ":" + TAG.format("0.1.0"))
    before = origin_state(repo)

    result = release(repo, "0.1.0")

    assert result.returncode == 1
    assert "not newer than 0.1.0" in result.stderr
    assert origin_state(repo) == before


def test_main_and_the_tag_reach_origin_together_or_not_at_all(repo: Path) -> None:
    origin = Path(git(repo, "remote", "get-url", "origin"))
    hook = origin / "hooks" / "update"  # runs per ref: accepts main, rejects any tag
    hook.write_text('#!/bin/sh\ncase "$1" in refs/tags/*) exit 1 ;; esac\n')
    hook.chmod(0o755)
    main_before = git(repo, "ls-remote", "origin", "refs/heads/main")

    result = release(repo, "patch")

    assert result.returncode != 0
    assert git(repo, "ls-remote", "origin", "refs/heads/main") == main_before
