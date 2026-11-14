"""scripts/prove-codex-release.sh, with a fake gh and a fake uv: no network, no real wheels."""

# ruff: noqa: E501 - the fakes are shell scripts in strings

import json
import subprocess
from pathlib import Path

import pytest
from conftest import posix_only

pytestmark = posix_only

SCRIPT = Path(__file__).parents[1] / "scripts" / "prove-codex-release.sh"
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
  "release list"*) cat "$FAKES/releases.json" ;;
  "api repos/Selimmo/claude-workbench/releases/tags/plan-review--v"*)
    tag="${2##*/}"
    version="${tag#plan-review--v}"
    zip='{"name":"plan-review-'"$version"'.zip","browser_download_url":"x.zip"}'
    if [ -e "$FAKES/no-wheel-$version" ]; then
      echo '{"assets":['"$zip"']}'
    else
      wheel='{"name":"plan_review-'"$version"'-py3-none-any.whl","browser_download_url":"@URL@/'"$tag"'/plan_review-'"$version"'-py3-none-any.whl"}'
      echo '{"assets":['"$zip"','"$wheel"']}'
    fi ;;
  *) echo "fake gh: unexpected $*" >&2; exit 1 ;;
esac
"""

# `uv tool install --force <url>` makes a fake plan-review at that version in UV_TOOL_BIN_DIR.
FAKE_UV = """#!/bin/sh
echo "uv $* HOME=$HOME CODEX_HOME=$CODEX_HOME TOOLS=$UV_TOOL_DIR BIN=$UV_TOOL_BIN_DIR" >> "$FAKES/calls.log"
[ "$1 $2 $3" = "tool install --force" ] || exit 1
version="$(basename "$4" | sed 's/^plan_review-//; s/-py3.*//')"
pkg="$UV_TOOL_DIR/plan-review/lib/site-packages/plan_review/harness/adapters/codex_files"
mkdir -p "$pkg/skills/ship/agents" "$pkg/agents"
echo "skill $version" > "$pkg/skills/ship/SKILL.md"
echo "policy $version" > "$pkg/skills/ship/agents/openai.yaml"
for role in grill-explorer architect implementer test-reviewer code-reviewer; do
  echo "agent $version" > "$pkg/agents/plan-review-$role.toml"
done
cat > "$UV_TOOL_BIN_DIR/plan-review" <<FAKE
#!/bin/sh
pkg="$pkg"
case "\\$1" in
  --version) echo "plan-review $version" ;;
  install)
    mkdir -p "\\$HOME/.agents/skills/ship/agents" "\\$CODEX_HOME/agents"
    cp "\\$pkg/skills/ship/SKILL.md" "\\$HOME/.agents/skills/ship/SKILL.md"
    cp "\\$pkg/skills/ship/agents/openai.yaml" "\\$HOME/.agents/skills/ship/agents/openai.yaml"
    for role in grill-explorer architect implementer test-reviewer code-reviewer; do
      [ -e "$FAKES/lose-\\$role" ] || cp "\\$pkg/agents/plan-review-\\$role.toml" "\\$CODEX_HOME/agents/"
    done ;;
  upgrade)
    newest="\\$(cat "$FAKES/newest")"
    "$FAKES/bin/uv" tool install --force "@URL@/plan-review--v\\$newest/plan_review-\\$newest-py3-none-any.whl"
    [ -e "$FAKES/no-rewrite" ] || "\\$0" install ;;
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
    (fakes / "newest").write_text("0.3.1")
    tags = ["plan-review--v0.3.1", "other--v9.9.9", "plan-review--v0.3.0", "plan-review--v0.2.0"]
    (fakes / "releases.json").write_text(json.dumps([{"tagName": tag} for tag in tags]))
    (fakes / "no-wheel-0.2.0").write_text("")
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


def test_prove_codex_installs_the_latest_wheel_in_a_throwaway_home(
    fakes: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    only_release(fakes, "plan-review--v0.3.0")
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "owners-own-codex"))
    work = tmp_path / "proof"

    result = prove(work)

    assert result.returncode == 0, result.stderr
    (call,) = (fakes / "calls.log").read_text().splitlines()
    assert call == (
        f"uv tool install --force {URL}/plan-review--v0.3.0/plan_review-0.3.0-py3-none-any.whl "
        f"HOME={work}/home CODEX_HOME={work}/home/.codex "
        f"TOOLS={work}/uv/tools BIN={work}/uv/bin"
    )
    assert not (tmp_path / "owners-own-codex").exists()


def test_prove_codex_fails_when_an_agent_file_is_missing(fakes: Path, tmp_path: Path) -> None:
    only_release(fakes, "plan-review--v0.3.0")
    (fakes / "lose-implementer").write_text("")

    result = prove(tmp_path / "proof")

    assert result.returncode == 1
    assert "plan-review-implementer.toml is missing" in result.stderr


def test_prove_codex_fails_when_the_grill_explorer_file_is_missing(
    fakes: Path, tmp_path: Path
) -> None:
    only_release(fakes, "plan-review--v0.3.0")
    (fakes / "lose-grill-explorer").write_text("")

    result = prove(tmp_path / "proof")

    assert result.returncode == 1
    assert "plan-review-grill-explorer.toml is missing" in result.stderr


def test_prove_codex_fails_when_the_installed_version_is_wrong(fakes: Path, tmp_path: Path) -> None:
    only_release(fakes, "plan-review--v0.3.0")
    uv = fakes / "bin" / "uv"
    uv.write_text(uv.read_text().replace('echo "plan-review $version"', "echo plan-review 9.9.9"))

    result = prove(tmp_path / "proof")

    assert result.returncode == 1
    assert "expected plan-review 0.3.0" in result.stderr


def test_prove_codex_upgrades_from_the_previous_release(fakes: Path, tmp_path: Path) -> None:
    result = prove(tmp_path / "proof")

    assert result.returncode == 0, result.stderr
    installs = [
        line.split()[4].rsplit("/", 1)[1] for line in (fakes / "calls.log").read_text().splitlines()
    ]
    assert installs == [
        "plan_review-0.3.0-py3-none-any.whl",  # the older one first (0.2.0 has no wheel)
        "plan_review-0.3.1-py3-none-any.whl",  # then its own upgrade
    ]
    assert result.stdout.strip().splitlines()[-1] == (
        "ok: plan-review 0.3.1, with the ship skill and the five agents"
    )


def test_prove_codex_fails_when_upgrade_leaves_the_old_files(fakes: Path, tmp_path: Path) -> None:
    (fakes / "no-rewrite").write_text("")

    result = prove(tmp_path / "proof")

    assert result.returncode == 1
    assert "differs from the files in the installed wheel" in result.stderr


def test_prove_codex_says_when_upgrade_cannot_be_proven_yet(fakes: Path, tmp_path: Path) -> None:
    only_release(fakes, "plan-review--v0.3.0")

    result = prove(tmp_path / "proof")

    assert result.returncode == 0, result.stderr
    assert "upgrade needs a second release" in result.stdout
    assert len(result.stdout.strip().splitlines()) == 2  # the install proof, and that one line


def test_prove_codex_needs_a_folder(fakes: Path) -> None:
    result = subprocess.run([str(SCRIPT)], capture_output=True, text=True, check=False)

    assert result.returncode == 2
    assert "usage: scripts/prove-codex-release.sh <dir>" in result.stderr


def test_prove_codex_fails_when_no_release_has_a_wheel(fakes: Path, tmp_path: Path) -> None:
    only_release(fakes, "plan-review--v0.2.0")  # its fake release has no wheel

    result = prove(tmp_path / "proof")

    assert result.returncode == 1
    assert "no plan-review release with a wheel" in result.stderr
    assert not (fakes / "calls.log").exists()


def test_prove_codex_asks_gh_as_the_owner_not_from_the_throwaway_home(
    fakes: Path, tmp_path: Path
) -> None:
    result = prove(tmp_path / "proof")

    assert result.returncode == 0, result.stderr
    assert "gh auth login" not in result.stderr


def test_prove_codex_says_so_when_gh_itself_fails(
    fakes: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "somebody-else"))  # gh has no login here

    result = prove(tmp_path / "proof")

    assert result.returncode != 0
    assert "no plan-review release with a wheel" not in result.stderr
