#!/usr/bin/env bash
# Release plan-review: ./release.sh <version|patch>
#
# Sets the version in plugin.json and pyproject.toml (and uv.lock), commits it on main,
# tags the commit plan-review--v<version> and pushes both. The tag starts the release
# workflow, which builds the plugin zip, attaches it to the GitHub release and points
# the marketplace entry at it.
set -euo pipefail
cd "$(dirname "$0")"

if [[ $# -ne 1 || ! "$1" =~ ^(patch|[0-9]+\.[0-9]+\.[0-9]+)$ ]]; then
  echo "usage: ./release.sh <version|patch>   (version: X.Y.Z)" >&2
  exit 2
fi

fail() {
  echo "release.sh: $*" >&2
  exit 1
}

[[ -z "$(git status --porcelain)" ]] || fail "uncommitted changes: commit or stash them first"

[[ "$(git branch --show-current)" == main ]] || fail "check out main first"
git fetch --quiet --tags origin main
[[ "$(git rev-parse HEAD)" == "$(git rev-parse origin/main)" ]] ||
  fail "main differs from origin/main: pull or push first"

prefix="plan-review--v"
last_tag="$(git tag --list "${prefix}*" --sort=-v:refname | head -n 1)"
current="$(jq -r .version .claude-plugin/plugin.json)"
# The last released version; before the first release, the version in plugin.json.
last="${last_tag#"$prefix"}"
last="${last:-$current}"

newer_than_last() {
  [[ "$1" != "$last" && "$(printf '%s\n%s\n' "$last" "$1" | sort -V | tail -n 1)" == "$1" ]]
}

if [[ "$1" != patch ]]; then
  version="$1"
elif newer_than_last "$current"; then
  version="$current" # a pull request already bumped it (the version guard asks for that)
else
  IFS=. read -r major minor patch <<<"$last"
  version="$major.$minor.$((patch + 1))"
fi
# Before the first release too: Claude Code may already have plugin.json's version cached.
if ! newer_than_last "$version"; then
  fail "$version is not newer than $last, the last release"
fi

scripts/set-version.sh "$version"
# Nothing to commit when a pull request already set this version.
if ! git diff --quiet; then
  git commit --quiet -m "Release plan-review v$version" -- .claude-plugin/plugin.json pyproject.toml uv.lock
fi
git tag -a "$prefix$version" -m "plan-review $version"
# Atomic: either main and the tag both reach origin, or neither does.
git push --quiet --atomic origin HEAD:main "$prefix$version"
echo "Pushed $prefix$version: the release workflow now builds and publishes the plugin zip."
