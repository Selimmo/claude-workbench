#!/usr/bin/env bash
# Set plan-review's version everywhere it is written: scripts/set-version.sh <version>
# plugin.json is what Claude Code reads; pyproject.toml (and uv.lock) what `plan-review
# --version` reports.
set -euo pipefail
cd "$(dirname "$0")/.."

version="$1"
manifest=".claude-plugin/plugin.json"
jq --arg v "$version" '.version = $v' "$manifest" >"$manifest.tmp"
mv "$manifest.tmp" "$manifest"
uv version --quiet --no-sync "$version"
