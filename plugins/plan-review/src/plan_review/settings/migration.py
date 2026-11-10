"""Finds the old `.claude/` files when they are the only ones, and words how to move them.

This is the one core module that may name them. It only finds and words: it never prints,
writes or moves anything, so reading an old project leaves it exactly as it was.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from plan_review.paths.workdir import config_path, preferences_path

# What comments.json and grill.json files saved before the agent was neutral hold.
LegacyAuthor = Literal["claude"]

_OLD_CONFIG = Path(".claude", "pipeline.json")
_OLD_PREFERENCES = Path(".claude", "work", "preferences.json")


@dataclass(frozen=True)
class Source:
    """Which file to read, and the one line to show if it is an old one."""

    path: Path
    move_hint: str | None = None


def config_source(root: Path) -> Source:
    new = config_path(root)
    old = root / _OLD_CONFIG
    if new.is_file() or not old.is_file():
        return Source(new)
    hint = f"plan-review: read {_OLD_CONFIG.as_posix()}; move it to .plan-review/config.json"
    return Source(old, hint)


def preferences_source(root: Path) -> Source:
    new = preferences_path(root)
    old = root / _OLD_PREFERENCES
    if new.is_file() or not old.is_file():
        return Source(new)
    hint = (
        f"plan-review: read {_OLD_PREFERENCES.as_posix()}; "
        "save it to .plan-review/work/ with `plan-review prefs grill <page|chat>`"
    )
    return Source(old, hint)
