#!/usr/bin/env bash
# Prove a release installs and upgrades, in a throwaway Claude Code config
# (CLAUDE_CONFIG_DIR=<dir>/config): your own ~/.claude is never touched.
#   scripts/prove-release.sh install <dir>   after a release
#   scripts/prove-release.sh upgrade <dir>   after the next release, with the same <dir>
# Run it in your own terminal: Claude Code asks you to accept the headers command.
#
# Made for test releases while the repo is private: they leave main's marketplace.json
# alone, so this builds a local copy whose plan-review entry is the latest release's zip.
# A private asset's download link takes no token, so the entry downloads it through the
# GitHub API with your gh login, sent by a headersHelper (which needs "strict": false).
set -euo pipefail
if [[ $# -ne 2 || ! "$1" =~ ^(install|upgrade)$ ]]; then
  echo "usage: scripts/prove-release.sh install|upgrade <dir>" >&2
  exit 2
fi
repo=Selimmo/claude-workbench
mode="$1"
dir="$(mkdir -p "$2" && cd "$2" && pwd)"
mkdir -p "$dir/.claude-plugin" "$dir/config" "$dir/zips"

tag="$(gh release list -R "$repo" --json tagName |
  jq -r '[.[].tagName | select(startswith("plan-review--v"))][0] // empty')"
if [[ -z "$tag" ]]; then
  echo "prove-release.sh: no plan-review release on $repo yet: run ./release.sh patch" >&2
  exit 1
fi
version="${tag#plan-review--v}"
# The release also holds the wheel, so pick the zip by name, not by position.
zip_asset='.assets[] | select(.name | endswith(".zip"))'
asset_id="$(gh api "repos/$repo/releases/tags/$tag" | jq -r "$zip_asset | .id")"
gh release download "$tag" -R "$repo" -p '*.zip' -D "$dir/zips" --clobber
sha256="$(shasum -a 256 "$dir/zips/plan-review-$version.zip" | cut -d ' ' -f 1)"

# Claude Code runs the helper with a cleaned environment from its config dir: give it gh's
# absolute path, and let gh read the token from its own login.
cat >"$dir/headers.sh" <<HELPER
#!/bin/sh
printf '{"Authorization":"Bearer %s","Accept":"application/octet-stream"}' "\$($(command -v gh) auth token)"
HELPER
chmod +x "$dir/headers.sh"

gh api "repos/$repo/contents/.claude-plugin/marketplace.json?ref=main" \
  -H "Accept: application/vnd.github.raw" |
  jq --arg u "https://api.github.com/repos/$repo/releases/assets/$asset_id" \
    --arg sha "$sha256" --arg v "$version" --arg h "$dir/headers.sh" '
    .plugins |= map(if .name == "plan-review" then
      .source = {source: "archive", url: $u, sha256: $sha} | .version = $v
      | .strict = false | .headersHelper = $h
    else . end)' >"$dir/.claude-plugin/marketplace.json"

downloads() { gh api "repos/$repo/releases/tags/$tag" | jq -r "$zip_asset | .download_count"; }
echo "$tag: asset $asset_id, $(downloads) downloads before Claude Code's"
export CLAUDE_CONFIG_DIR="$dir/config"
cache="$dir/config/plugins/cache/claude-workbench/plan-review"
case "$mode" in
  install) claude plugin install plan-review --marketplace "$dir" ;;
  upgrade)
    installed=("$cache"/*/bin/plan-review)
    if [[ ! -x "${installed[0]}" ]]; then
      echo "prove-release.sh: no plan-review installed in $dir: run install first" >&2
      exit 1
    fi
    "${installed[0]}" upgrade
    ;;
esac
echo "$tag: $(downloads) downloads now"
echo "installed plan-review versions: $(find "$cache" -mindepth 1 -maxdepth 1 -type d -exec basename {} \; | sort -V | xargs)"
