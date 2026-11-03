#!/usr/bin/env bash
# Point the marketplace's plan-review entry at a released zip:
#   scripts/set-marketplace-entry.sh <marketplace.json> <version> <url> <sha256>
# The release workflow runs it after attaching the zip to the GitHub release.
set -euo pipefail

file="$1"
if ! jq -e 'any(.plugins[]; .name == "plan-review")' "$file" >/dev/null; then
  echo "set-marketplace-entry.sh: $file has no plan-review entry" >&2
  exit 1
fi
jq --arg v "$2" --arg url "$3" --arg sha "$4" '
  .plugins |= map(
    if .name == "plan-review"
    then .source = {source: "archive", url: $url, sha256: $sha} | .version = $v
    else . end
  )' "$file" >"$file.tmp"
mv "$file.tmp" "$file"
