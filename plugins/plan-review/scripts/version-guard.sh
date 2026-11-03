#!/usr/bin/env bash
# Fail when files that end up in the plugin zip changed since the release of the version
# in plugin.json. Claude Code only fetches a plugin again when its version changes, so
# such a change could never reach users: bump the version (scripts/set-version.sh).
# Needs the release tags (CI: actions/checkout with fetch-depth: 0).
set -euo pipefail
cd "$(dirname "$0")/.."

version="$(jq -r .version .claude-plugin/plugin.json)"
tag="plan-review--v$version"
if ! git rev-parse --quiet --verify "refs/tags/$tag" >/dev/null; then
  echo "version-guard: $version is not released yet"
  exit 0
fi
# What the zip holds: the shipped files, and what the built page and LICENSE come from.
# (The page's tests do not ship.) bash 3.2 has no mapfile.
paths=(":(exclude,glob)web/src/**/*.test.*")
while read -r path; do paths+=("$path"); done < <(cat scripts/shipped-paths scripts/build-inputs)

changed="$(git diff --name-only "$tag" HEAD -- "${paths[@]}")"
if [[ -n "$changed" ]]; then
  echo "version-guard: these files changed since $tag, but the version is still $version:" >&2
  echo "$changed" >&2
  exit 1
fi
