"""One adapter per CLI that can run the agents."""

from pathlib import Path

from plan_review.adapters.claude_code import ClaudeCode
from plan_review.adapters.codex import Codex
from plan_review.harness import Adapter

ADAPTERS: tuple[Adapter, ...] = (ClaudeCode(), Codex())


def installed_adapter(package_root: Path) -> Adapter | None:
    """The adapter whose CLI installed the copy of plan-review in `package_root`, if any."""
    return next((a for a in ADAPTERS if a.installed_at(package_root)), None)


def adapter_by_key(key: str) -> Adapter | None:
    return next((a for a in ADAPTERS if a.key == key), None)
