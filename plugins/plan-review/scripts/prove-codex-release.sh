#!/usr/bin/env bash
# Prove plan-review installs and upgrades for Codex from the real release wheels, in a
# throwaway home folder: your own ~/.agents, ~/.codex and uv tools are never touched.
#   scripts/prove-codex-release.sh <dir>
# Run it after a release that has a wheel. With two such releases it installs the older one,
# runs that copy's own `plan-review upgrade`, and checks the newest is there afterwards. With
# one it proves the install and says the upgrade needs a second release. It does not start
# Codex: it checks the version, the ship skill and the four agent files.
set -euo pipefail
if [[ $# -ne 1 ]]; then
  echo "usage: scripts/prove-codex-release.sh <dir>" >&2
  exit 2
fi
repo=Selimmo/claude-workbench
dir="$(mkdir -p "$1" && cd "$1" && pwd)"

# Newest first: each plan-review release that carries a wheel, as "<version> <url>".
# Asked before HOME moves: gh keeps the owner's login in their own home folder. Each gh call
# is its own statement, so a gh failure stops the script instead of looking like "no release".
tags="$(gh release list -R "$repo" --json tagName)"
tags="$(jq -r '.[].tagName | select(startswith("plan-review--v"))' <<<"$tags")"
wheels=()
while read -r tag; do
  [[ -n "$tag" ]] || continue
  release="$(gh api "repos/$repo/releases/tags/$tag")"
  url="$(jq -r '[.assets[] | select(.name | endswith(".whl")) | .browser_download_url][0] // empty' <<<"$release")"
  [[ -z "$url" ]] || wheels+=("${tag#plan-review--v} $url")
done <<<"$tags"
if [[ ${#wheels[@]} -eq 0 ]]; then
  echo "prove-codex-release.sh: no plan-review release with a wheel on $repo yet" >&2
  exit 1
fi

# Everything lands inside <dir>, whatever the owner has set.
export HOME="$dir/home"
export CODEX_HOME="$dir/home/.codex"
export UV_TOOL_DIR="$dir/uv/tools"
export UV_TOOL_BIN_DIR="$dir/uv/bin"
mkdir -p "$HOME" "$UV_TOOL_DIR" "$UV_TOOL_BIN_DIR"
export PATH="$UV_TOOL_BIN_DIR:$PATH"

check() { # <version>: the installed copy is that version, and the files in the home folder are its own
  local want="$1" got
  got="$(plan-review --version)"
  [[ "$got" == "plan-review $want" ]] || {
    echo "FAIL: expected plan-review $want, got '$got'" >&2
    exit 1
  }
  local file
  for file in \
    "$HOME/.agents/skills/ship/SKILL.md" \
    "$HOME/.agents/skills/ship/agents/openai.yaml" \
    "$CODEX_HOME/agents/plan-review-architect.toml" \
    "$CODEX_HOME/agents/plan-review-implementer.toml" \
    "$CODEX_HOME/agents/plan-review-test-reviewer.toml" \
    "$CODEX_HOME/agents/plan-review-code-reviewer.toml"; do
    [[ -f "$file" ]] || {
      echo "FAIL: $file is missing" >&2
      exit 1
    }
  done
  # The files must be the ones this wheel carries, whoever wrote them: an upgrade that left
  # the old skill and agents behind fails here.
  local pkg
  pkg="$(find "$UV_TOOL_DIR" -type d -path '*/plan_review/harness/adapters/codex_files' | head -n 1)"
  [[ -n "$pkg" ]] || {
    echo "FAIL: the installed wheel holds no codex_files" >&2
    exit 1
  }
  diff -r "$pkg/skills" "$HOME/.agents/skills" >/dev/null &&
    diff -r "$pkg/agents" "$CODEX_HOME/agents" >/dev/null || {
    echo "FAIL: plan-review $want: a file differs from the files in the installed wheel" >&2
    exit 1
  }
  echo "ok: plan-review $want, with the ship skill and the four agents"
}

latest_version="${wheels[0]%% *}"
if [[ ${#wheels[@]} -ge 2 ]]; then
  older_version="${wheels[1]%% *}"
  uv tool install --force "${wheels[1]#* }"
  plan-review install codex >/dev/null
  check "$older_version"
  plan-review upgrade # writes the files itself: nothing here does it for it
  check "$latest_version"
else
  uv tool install --force "${wheels[0]#* }"
  plan-review install codex >/dev/null
  check "$latest_version"
  echo "the upgrade needs a second release with a wheel: run this again after the next release"
fi
