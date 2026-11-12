#!/usr/bin/env bash
# Prove plan-review installs and upgrades for opencode from the real release wheels, in a
# throwaway home folder: your own ~/.config/opencode, ~/.agents and uv tools are never touched.
#   scripts/prove-opencode-release.sh <dir>
# Run it after a release that has a wheel with opencode's files. With two such releases it
# installs the older one, runs that copy's own `plan-review upgrade`, and checks the newest is
# there afterwards. With one (or when the older wheel has no opencode files) it proves the
# install and says the upgrade needs a second release with opencode. It does not start
# opencode: it checks the version, the /plan-review-ship command and the four agent files, and
# that the Codex ship skill was not written.
set -euo pipefail
if [[ $# -ne 1 ]]; then
  echo "usage: scripts/prove-opencode-release.sh <dir>" >&2
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
  echo "prove-opencode-release.sh: no plan-review release with a wheel on $repo yet" >&2
  exit 1
fi

# Everything lands inside <dir>, whatever the owner has set: opencode's folder is then
# $HOME/.config/opencode.
export HOME="$dir/home"
unset XDG_CONFIG_HOME CODEX_HOME
export UV_TOOL_DIR="$dir/uv/tools"
export UV_TOOL_BIN_DIR="$dir/uv/bin"
mkdir -p "$HOME" "$UV_TOOL_DIR" "$UV_TOOL_BIN_DIR"
export PATH="$UV_TOOL_BIN_DIR:$PATH"
config="$HOME/.config/opencode"

wheel_files() { # the opencode_files folder of the installed wheel, or nothing
  find "$UV_TOOL_DIR" -type d -path '*/plan_review/harness/adapters/opencode_files' | head -n 1
}

check() { # <version>: the installed copy is that version, and the files in the home folder are its own
  local want="$1" got
  got="$(plan-review --version)"
  [[ "$got" == "plan-review $want" ]] || {
    echo "FAIL: expected plan-review $want, got '$got'" >&2
    exit 1
  }
  local file
  for file in \
    "$config/commands/plan-review-ship.md" \
    "$config/agents/plan-review-architect.md" \
    "$config/agents/plan-review-implementer.md" \
    "$config/agents/plan-review-test-reviewer.md" \
    "$config/agents/plan-review-code-reviewer.md"; do
    [[ -f "$file" ]] || {
      echo "FAIL: $file is missing" >&2
      exit 1
    }
  done
  [[ ! -e "$HOME/.agents/skills/ship" ]] || {
    echo "FAIL: $HOME/.agents/skills/ship was written: opencode must leave the Codex skill alone" >&2
    exit 1
  }
  # The files must be the ones this wheel carries, whoever wrote them: an upgrade that left
  # the old command and agents behind fails here.
  local pkg
  pkg="$(wheel_files)"
  [[ -n "$pkg" ]] || {
    echo "FAIL: the installed wheel holds no opencode_files" >&2
    exit 1
  }
  diff -r "$pkg/commands" "$config/commands" >/dev/null &&
    diff -r "$pkg/agents" "$config/agents" >/dev/null || {
    echo "FAIL: plan-review $want: a file differs from the files in the installed wheel" >&2
    exit 1
  }
  echo "ok: plan-review $want, with the command and the four agents"
}

latest_version="${wheels[0]%% *}"
proved_upgrade=0
if [[ ${#wheels[@]} -ge 2 ]]; then
  older_version="${wheels[1]%% *}"
  uv tool install --force "${wheels[1]#* }"
  if [[ -n "$(wheel_files)" ]]; then
    plan-review install opencode >/dev/null
    check "$older_version"
    plan-review upgrade # writes the files itself: nothing here does it for it
    check "$latest_version"
    proved_upgrade=1
  fi
fi
if [[ $proved_upgrade -eq 0 ]]; then
  uv tool install --force "${wheels[0]#* }"
  plan-review install opencode >/dev/null
  check "$latest_version"
  echo "the upgrade needs a second release with opencode's files: run this again after the next release"
fi
