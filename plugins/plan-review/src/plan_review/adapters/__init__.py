"""One adapter per CLI that can run the agents."""

from pathlib import Path

from plan_review.adapters.claude_code import ClaudeCode
from plan_review.harness import Adapter

ADAPTERS: tuple[Adapter, ...] = (ClaudeCode(),)


def installed_adapter(package_root: Path) -> Adapter | None:
    """The adapter whose CLI installed the copy of plan-review in `package_root`, if any."""
    return next((a for a in ADAPTERS if a.installed_at(package_root)), None)
