"""scripts/link-release.sh: point main's marketplace.json at a release, once it is public.

While the repo is private, releases are test releases: anyone without access would get
a 404 from the zip's URL, so main's marketplace.json is left alone.
"""

import json
import subprocess
from pathlib import Path

import pytest
from conftest import git

URL = "https://github.com/o/r/releases/download/plan-review--v0.1.1/plan-review-0.1.1.zip"
SHA = "cd" * 32
MARKETPLACE = "origin/main:.claude-plugin/marketplace.json"


def link(plugin: Path, visibility: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["scripts/link-release.sh", visibility, "0.1.1", URL, SHA],
        cwd=plugin,
        capture_output=True,
        text=True,
        check=False,
    )


def origin_entry(plugin: Path) -> dict[str, object]:
    git(plugin, "fetch", "--quiet", "origin")
    return json.loads(git(plugin, "show", MARKETPLACE))["plugins"][0]


@pytest.mark.parametrize("visibility", ["PRIVATE", "INTERNAL"])
def test_a_repo_that_is_not_public_leaves_the_marketplace_alone(
    repo: Path, visibility: str
) -> None:
    before = git(repo, "ls-remote", "origin", "refs/heads/main")

    result = link(repo, visibility)

    assert result.returncode == 0, result.stderr
    assert "test release" in result.stdout
    assert git(repo, "ls-remote", "origin", "refs/heads/main") == before


def test_a_public_repos_release_points_mains_marketplace_at_the_zip(repo: Path) -> None:
    result = link(repo, "PUBLIC")

    assert result.returncode == 0, result.stderr
    entry = origin_entry(repo)
    assert entry["source"] == {"source": "archive", "url": URL, "sha256": SHA}
    assert entry["version"] == "0.1.1"


def test_running_it_again_changes_nothing_and_succeeds(repo: Path) -> None:
    # A re-run of a release workflow whose link step already went through.
    link(repo, "PUBLIC")
    linked = git(repo, "ls-remote", "origin", "refs/heads/main")

    result = link(repo, "PUBLIC")

    assert result.returncode == 0, result.stderr
    assert git(repo, "ls-remote", "origin", "refs/heads/main") == linked


def test_retries_on_top_of_a_main_that_moved_on_while_it_pushed(repo: Path, tmp_path: Path) -> None:
    # A pull request is merged between its fetch and its push: the push is rejected, and
    # the retry must start from the new main, keeping that change.
    origin = git(repo, "remote", "get-url", "origin")
    other = tmp_path / "other"
    hook = repo.parents[1] / ".git" / "hooks" / "pre-push"
    hook.write_text(
        "#!/bin/sh\n"
        f"[ -e {tmp_path}/merged ] && exit 0\n"
        f"touch {tmp_path}/merged\n"
        "unset GIT_DIR GIT_INDEX_FILE\n"
        f"git clone --quiet {origin} {other} && cd {other} &&\n"
        "echo merged > notes.md && git add notes.md && git commit --quiet -m Merged &&\n"
        "git push --quiet origin main\n"
    )
    hook.chmod(0o755)

    result = link(repo, "PUBLIC")

    assert result.returncode == 0, result.stderr
    assert origin_entry(repo)["version"] == "0.1.1"
    assert git(repo, "show", "origin/main:notes.md") == "merged"


def test_gives_up_with_exit_1_when_main_keeps_rejecting_the_push(repo: Path) -> None:
    origin = Path(git(repo, "remote", "get-url", "origin"))
    hook = origin / "hooks" / "update"
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o755)

    result = link(repo, "PUBLIC")

    assert result.returncode == 1
    assert "re-run the release workflow" in result.stderr
