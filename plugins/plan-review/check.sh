#!/usr/bin/env bash
# Run every plan-review check; exits non-zero on the first failure.
set -euo pipefail
cd "$(dirname "$0")"

npm --prefix web run check   # first: builds the page the Python package serves
uv run ruff check
uv run ruff format --check
uv run pyright
uv run python -m plan_review.harness.generate --check  # generated skill and agents are fresh
uv run pytest
