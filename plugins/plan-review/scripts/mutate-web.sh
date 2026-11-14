#!/usr/bin/env bash
# Mutation-test the web viewer with StrykerJS, on only the web source files this branch touched:
# committed since it left main, changed but not committed, or new. Tests are left out. With no
# such file, Stryker is skipped. Run from the plugin folder; STRYKER overrides the command.
set -euo pipefail

base=$(git merge-base HEAD main 2>/dev/null || git merge-base HEAD origin/main)

files=$(
  {
    git diff --name-only --relative "$base" -- web/src
    git ls-files --others --exclude-standard -- web/src
  } | grep -E '\.tsx?$' | grep -vE '\.test\.tsx?$|^web/src/test/' | sort -u |
    while read -r path; do [ -f "$path" ] && echo "${path#web/}"; done || true
)

if [ -z "$files" ]; then
  echo "mutate-web: no web source changed since main; Stryker skipped"
  exit 0
fi

cd web
${STRYKER:-npx stryker} run --mutate "$(echo "$files" | paste -sd, -)"
