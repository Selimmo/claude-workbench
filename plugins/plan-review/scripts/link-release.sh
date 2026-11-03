#!/usr/bin/env bash
# Point main's marketplace.json at a released zip, once the repo is public:
#   scripts/link-release.sh <visibility> <version> <url> <sha256>
# <visibility> is GitHub's (PUBLIC, PRIVATE, INTERNAL). The release workflow runs it last.
# Safe to re-run: an entry that already points at the zip is left as it is.
set -euo pipefail
cd "$(dirname "$0")/.."

visibility="$1"
if [[ "$visibility" != PUBLIC ]]; then
  echo "link-release: the repo is $visibility, so this is a test release: marketplace.json on main is left alone"
  exit 0
fi

version="$2"
marketplace=../../.claude-plugin/marketplace.json
# Main can move on between the fetch and the push (a merged pull request): start again
# from the new main, a few times.
for attempt in 1 2 3; do
  git fetch --quiet origin main
  git checkout --quiet -B main origin/main
  scripts/set-marketplace-entry.sh "$marketplace" "$version" "$3" "$4"
  if git diff --quiet -- "$marketplace"; then
    echo "link-release: main already points at plan-review $version"
    exit 0
  fi
  git commit --quiet -m "Point the marketplace at plan-review $version" -- "$marketplace"
  if git push --quiet origin main; then
    echo "link-release: main now points at plan-review $version"
    exit 0
  fi
  echo "link-release: push $attempt rejected; retrying on the new main" >&2
done
echo "link-release: could not push to main; re-run the release workflow" >&2
exit 1
