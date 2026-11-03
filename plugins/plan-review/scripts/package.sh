#!/usr/bin/env bash
# Build the release zip: scripts/package.sh <out-dir>; prints the zip's path.
# Holds the files in scripts/shipped-paths (the viewer page must be built first) and the
# repo's LICENSE, with the plugin root at the top of the zip, as Claude Code expects.
set -euo pipefail
out="$(cd "$1" && pwd)" # before the cd below: a relative <out-dir> is the caller's
cd "$(dirname "$0")/.."

if [[ ! -f src/plan_review/static/index.html ]]; then
  echo "package.sh: the viewer page is not built: run npm --prefix web run build" >&2
  exit 1
fi

version="$(jq -r .version .claude-plugin/plugin.json)"
zip_file="$out/plan-review-$version.zip"

stage="$(mktemp -d)"
trap 'rm -rf "$stage"' EXIT
while read -r path; do
  mkdir -p "$stage/$(dirname "$path")"
  cp -Rp "$path" "$stage/$path"
done <scripts/shipped-paths
cp ../../LICENSE "$stage/LICENSE"
find "$stage" \( -name __pycache__ -o -name .DS_Store \) -prune -exec rm -rf {} +

rm -f "$zip_file"
(cd "$stage" && zip -qrX "$zip_file" .)
echo "$zip_file"
