"""scripts/prove-release.sh: install or upgrade from a (private) test release, in a throwaway
Claude Code config. Here `gh` and `claude` are fakes: no network, no real Claude Code."""

import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

import pytest

PLUGIN = Path(__file__).parents[1]
SCRIPT = PLUGIN / "scripts" / "prove-release.sh"
API = "https://api.github.com/repos/Selimmo/claude-workbench/releases/assets"

FAKE_GH = """#!/bin/sh
case "$*" in
  "release list"*) cat "$FAKES/releases.json" ;;
  "api repos/Selimmo/claude-workbench/releases/tags/"*) cat "$FAKES/release.json" ;;
  "api repos/Selimmo/claude-workbench/contents/"*) cat "$FAKES/marketplace.json" ;;
  "release download"*)
    dest=""; prev=""
    for arg in "$@"; do [ "$prev" = "-D" ] && dest="$arg"; prev="$arg"; done
    cp "$FAKES"/*.zip "$dest/" ;;
  "auth token") echo gho_fake ;;
  *) echo "fake gh: unexpected $*" >&2; exit 1 ;;
esac
"""
FAKE_CLAUDE = """#!/bin/sh
echo "CLAUDE_CONFIG_DIR=$CLAUDE_CONFIG_DIR claude $*" >> "$FAKES/calls.log"
"""


@pytest.fixture
def fakes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Fake gh and claude on PATH, answering from files in the returned folder."""
    fakes = tmp_path / "fakes"
    bin_dir = fakes / "bin"
    bin_dir.mkdir(parents=True)
    for name, text in [("gh", FAKE_GH), ("claude", FAKE_CLAUDE)]:
        (bin_dir / name).write_text(text)
        (bin_dir / name).chmod(0o755)
    releases = [{"tagName": "other--v9.0.0"}, {"tagName": "plan-review--v0.1.2"}]
    (fakes / "releases.json").write_text(
        json.dumps(releases + [{"tagName": "plan-review--v0.1.1"}])
    )
    (fakes / "release.json").write_text(json.dumps({"assets": [{"id": 4242, "download_count": 3}]}))
    marketplace = {
        "name": "claude-workbench",
        "plugins": [{"name": "plan-review", "source": "./p"}],
    }
    (fakes / "marketplace.json").write_text(json.dumps(marketplace))
    with zipfile.ZipFile(fakes / "plan-review-0.1.2.zip", "w") as zip_file:
        zip_file.writestr("README.md", "plan-review")
    monkeypatch.setenv("FAKES", str(fakes))
    monkeypatch.setenv("PATH", f"{bin_dir}:/usr/bin:/bin")
    return fakes


def prove(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(SCRIPT), *args], capture_output=True, text=True, check=False)


def test_the_marketplace_offers_the_latest_releases_zip_through_the_api(
    fakes: Path, tmp_path: Path
) -> None:
    work = tmp_path / "proof"

    result = prove("install", str(work))

    assert result.returncode == 0, result.stderr
    marketplace = json.loads((work / ".claude-plugin" / "marketplace.json").read_text())
    (entry,) = marketplace["plugins"]
    zip_sha = hashlib.sha256((fakes / "plan-review-0.1.2.zip").read_bytes()).hexdigest()
    assert entry == {
        "name": "plan-review",
        "source": {"source": "archive", "url": f"{API}/4242", "sha256": zip_sha},
        "version": "0.1.2",
        "strict": False,
        "headersHelper": str(work / "headers.sh"),
    }


def test_the_headers_helper_sends_the_gh_login_and_asks_for_the_file(
    fakes: Path, tmp_path: Path
) -> None:
    work = tmp_path / "proof"
    prove("install", str(work))

    headers = subprocess.run([str(work / "headers.sh")], capture_output=True, text=True)

    assert json.loads(headers.stdout) == {
        "Authorization": "Bearer gho_fake",
        "Accept": "application/octet-stream",  # the API's asset URL sends JSON otherwise
    }


def calls(fakes: Path) -> list[str]:
    return (fakes / "calls.log").read_text().splitlines()


def test_install_installs_into_the_throwaway_config(fakes: Path, tmp_path: Path) -> None:
    work = tmp_path / "proof"

    prove("install", str(work))

    assert (
        f"CLAUDE_CONFIG_DIR={work}/config claude plugin install plan-review --marketplace {work}"
        in calls(fakes)
    )


def test_upgrade_runs_the_installed_copys_own_upgrade(fakes: Path, tmp_path: Path) -> None:
    work = tmp_path / "proof"
    installed = work / "config/plugins/cache/claude-workbench/plan-review/0.1.1/bin/plan-review"
    installed.parent.mkdir(parents=True)
    installed.write_text(FAKE_CLAUDE.replace("claude $*", "plan-review $*"))
    installed.chmod(0o755)

    result = prove("upgrade", str(work))

    assert result.returncode == 0, result.stderr
    assert f"CLAUDE_CONFIG_DIR={work}/config plan-review upgrade" in calls(fakes)
    assert not [call for call in calls(fakes) if "plugin install" in call]


@pytest.mark.parametrize("args", [(), ("install",), ("remove", "dir")])
def test_anything_but_install_or_upgrade_and_a_folder_prints_the_usage(
    fakes: Path, args: tuple[str, ...]
) -> None:
    result = prove(*args)

    assert result.returncode == 2
    assert "usage: scripts/prove-release.sh install|upgrade <dir>" in result.stderr


def test_without_any_plan_review_release_says_so(fakes: Path, tmp_path: Path) -> None:
    (fakes / "releases.json").write_text(json.dumps([{"tagName": "other--v9.0.0"}]))

    result = prove("install", str(tmp_path / "proof"))

    assert result.returncode == 1
    assert "no plan-review release" in result.stderr


def test_upgrade_before_any_install_says_to_install_first(fakes: Path, tmp_path: Path) -> None:
    result = prove("upgrade", str(tmp_path / "proof"))

    assert result.returncode == 1
    assert "run install first" in result.stderr


def test_ends_by_listing_the_versions_in_the_throwaway_cache(fakes: Path, tmp_path: Path) -> None:
    work = tmp_path / "proof"
    cache = work / "config/plugins/cache/claude-workbench/plan-review"
    for version in ["0.1.1", "0.1.2"]:
        (cache / version).mkdir(parents=True)

    result = prove("install", str(work))

    assert result.stdout.splitlines()[-1] == "installed plan-review versions: 0.1.1 0.1.2"
