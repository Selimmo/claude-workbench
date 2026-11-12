"""scripts/prove-opencode-release.sh, with a fake gh and a fake uv: no network, no real wheels."""

# ruff: noqa: E501 - the fakes are shell scripts in strings

import json
import subprocess
from pathlib import Path

import pytest
from conftest import posix_only

pytestmark = posix_only

SCRIPT = Path(__file__).parents[1] / "scripts" / "prove-opencode-release.sh"
URL = "https://github.com/Selimmo/claude-workbench/releases/download"

FAKE_GH = """#!/bin/sh
case "$*" in
  "release list"* | "api repos/"*)
    # like the real gh: the owner's login lives in their own home folder
    if [ "$HOME" != "$REAL_HOME" ] && [ -z "$GH_TOKEN" ]; then
      echo "To get started with GitHub CLI, please run: gh auth login" >&2
      exit 4
    fi ;;
esac
case "$*" in
  "release list"*) [ -e "$FAKES/gh-fails" ] && exit 1; cat "$FAKES/releases.json" ;;
  "api repos/Selimmo/claude-workbench/releases/tags/plan-review--v"*)
    tag="${2##*/}"
    version="${tag#plan-review--v}"
    wheel='{"name":"plan_review-'"$version"'-py3-none-any.whl","browser_download_url":"@URL@/'"$tag"'/plan_review-'"$version"'-py3-none-any.whl"}'
    echo '{"assets":['"$wheel"']}' ;;
  *) echo "fake gh: unexpected $*" >&2; exit 1 ;;
esac
"""

# `uv tool install --force <url>` makes a fake plan-review at that version in UV_TOOL_BIN_DIR.
# A version with a `no-opencode-<version>` marker has a wheel without opencode_files.
FAKE_UV = """#!/bin/sh
echo "uv $* HOME=$HOME XDG=${XDG_CONFIG_HOME-unset} TOOLS=$UV_TOOL_DIR BIN=$UV_TOOL_BIN_DIR" >> "$FAKES/calls.log"
[ "$1 $2 $3" = "tool install --force" ] || exit 1
version="$(basename "$4" | sed 's/^plan_review-//; s/-py3.*//')"
rm -rf "$UV_TOOL_DIR/plan-review"
pkg="$UV_TOOL_DIR/plan-review/lib/site-packages/plan_review/harness/adapters/opencode_files"
if [ ! -e "$FAKES/no-opencode-$version" ]; then
  mkdir -p "$pkg/commands" "$pkg/agents"
  echo "command $version" > "$pkg/commands/plan-review-ship.md"
  for role in architect implementer test-reviewer code-reviewer; do
    echo "agent $version" > "$pkg/agents/plan-review-$role.md"
  done
fi
cat > "$UV_TOOL_BIN_DIR/plan-review" <<FAKE
#!/bin/sh
pkg="$pkg"
case "\\$1" in
  --version) echo "plan-review $version" ;;
  install)
    [ -d "\\$pkg" ] || { echo "invalid choice: opencode" >&2; exit 2; }
    mkdir -p "\\$HOME/.config/opencode"
    [ -e "$FAKES/also-codex" ] && mkdir -p "\\$HOME/.agents/skills/ship" && echo codex > "\\$HOME/.agents/skills/ship/SKILL.md"
    cp -R "\\$pkg/commands" "\\$pkg/agents" "\\$HOME/.config/opencode/"
    [ -e "$FAKES/lose-agent" ] && rm "\\$HOME/.config/opencode/agents/plan-review-implementer.md"
    true ;;
  upgrade)
    newest="\\$(cat "$FAKES/newest")"
    "$FAKES/bin/uv" tool install --force "@URL@/plan-review--v\\$newest/plan_review-\\$newest-py3-none-any.whl"
    [ -e "$FAKES/no-rewrite" ] || "\\$0" install opencode ;;
esac
FAKE
chmod +x "$UV_TOOL_BIN_DIR/plan-review"
"""


@pytest.fixture
def fakes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    fakes = tmp_path / "fakes"
    (fakes / "bin").mkdir(parents=True)
    for name, text in [("gh", FAKE_GH), ("uv", FAKE_UV)]:
        (fakes / "bin" / name).write_text(text.replace("@URL@", URL))
        (fakes / "bin" / name).chmod(0o755)
    (fakes / "newest").write_text("0.5.1")
    tags = ["plan-review--v0.5.1", "other--v9.9.9", "plan-review--v0.5.0", "plan-review--v0.4.0"]
    (fakes / "releases.json").write_text(json.dumps([{"tagName": tag} for tag in tags]))
    monkeypatch.setenv("FAKES", str(fakes))
    monkeypatch.setenv("REAL_HOME", str(tmp_path / "owner-home"))
    monkeypatch.setenv("HOME", str(tmp_path / "owner-home"))
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.setenv("PATH", f"{fakes / 'bin'}:/usr/bin:/bin")
    return fakes


def only_release(fakes: Path, tag: str) -> None:
    (fakes / "releases.json").write_text(json.dumps([{"tagName": tag}]))


def prove(folder: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(SCRIPT), str(folder)], capture_output=True, text=True, check=False)


def test_prove_opencode_release_proves_the_install(
    fakes: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    only_release(fakes, "plan-review--v0.5.0")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "owners-own-config"))
    work = tmp_path / "proof"

    result = prove(work)

    assert result.returncode == 0, result.stderr
    (call,) = (fakes / "calls.log").read_text().splitlines()
    assert call == (
        f"uv tool install --force {URL}/plan-review--v0.5.0/plan_review-0.5.0-py3-none-any.whl "
        f"HOME={work}/home XDG=unset TOOLS={work}/uv/tools BIN={work}/uv/bin"
    )
    assert not (tmp_path / "owners-own-config").exists()
    assert "ok: plan-review 0.5.0, with the command and the four agents" in result.stdout
    assert "upgrade needs a second release" in result.stdout


def test_prove_opencode_release_fails_when_an_agent_is_missing(fakes: Path, tmp_path: Path) -> None:
    only_release(fakes, "plan-review--v0.5.0")
    (fakes / "lose-agent").write_text("")

    result = prove(tmp_path / "proof")

    assert result.returncode == 1
    assert "plan-review-implementer.md is missing" in result.stderr


def test_prove_opencode_release_fails_when_the_version_is_wrong(
    fakes: Path, tmp_path: Path
) -> None:
    only_release(fakes, "plan-review--v0.5.0")
    uv = fakes / "bin" / "uv"
    uv.write_text(uv.read_text().replace('echo "plan-review $version"', "echo plan-review 9.9.9"))

    result = prove(tmp_path / "proof")

    assert result.returncode == 1
    assert "expected plan-review 0.5.0" in result.stderr


def test_prove_opencode_release_fails_when_the_codex_skill_appears(
    fakes: Path, tmp_path: Path
) -> None:
    only_release(fakes, "plan-review--v0.5.0")
    (fakes / "also-codex").write_text("")

    result = prove(tmp_path / "proof")

    assert result.returncode == 1
    assert "skills/ship" in result.stderr


def test_prove_opencode_release_proves_the_upgrade(fakes: Path, tmp_path: Path) -> None:
    result = prove(tmp_path / "proof")

    assert result.returncode == 0, result.stderr
    installs = [
        line.split()[4].rsplit("/", 1)[1] for line in (fakes / "calls.log").read_text().splitlines()
    ]
    assert installs == [
        "plan_review-0.5.0-py3-none-any.whl",  # the older one first
        "plan_review-0.5.1-py3-none-any.whl",  # then its own upgrade
    ]
    assert result.stdout.strip().splitlines()[-1] == (
        "ok: plan-review 0.5.1, with the command and the four agents"
    )


def test_prove_opencode_release_fails_when_upgrade_leaves_the_old_files(
    fakes: Path, tmp_path: Path
) -> None:
    (fakes / "no-rewrite").write_text("")

    result = prove(tmp_path / "proof")

    assert result.returncode == 1
    assert "differs from the files in the installed wheel" in result.stderr


def test_prove_opencode_release_proves_only_the_install_when_the_older_wheel_has_no_opencode(
    fakes: Path, tmp_path: Path
) -> None:
    (fakes / "no-opencode-0.5.0").write_text("")

    result = prove(tmp_path / "proof")

    assert result.returncode == 0, result.stderr
    installs = [
        line.split()[4].rsplit("/", 1)[1] for line in (fakes / "calls.log").read_text().splitlines()
    ]
    assert installs[-1] == "plan_review-0.5.1-py3-none-any.whl"
    assert "ok: plan-review 0.5.1, with the command and the four agents" in result.stdout
    assert "the upgrade needs a second release with opencode" in result.stdout


def test_prove_opencode_release_needs_a_folder(fakes: Path) -> None:
    result = subprocess.run([str(SCRIPT)], capture_output=True, text=True, check=False)

    assert result.returncode == 2
    assert "usage: scripts/prove-opencode-release.sh <dir>" in result.stderr


def test_prove_opencode_release_fails_when_no_release_has_a_wheel(
    fakes: Path, tmp_path: Path
) -> None:
    only_release(fakes, "other--v9.9.9")

    result = prove(tmp_path / "proof")

    assert result.returncode == 1
    assert "no plan-review release with a wheel" in result.stderr
    assert not (fakes / "calls.log").exists()


def test_prove_opencode_release_stops_when_gh_fails(fakes: Path, tmp_path: Path) -> None:
    (fakes / "gh-fails").write_text("")

    result = prove(tmp_path / "proof")

    assert result.returncode != 0
    assert "no plan-review release with a wheel" not in result.stderr
    assert not (fakes / "calls.log").exists()
