"""Finds the old `.claude/` files when they are the only ones, and moves the grill choice.

This is the one core module that may name them. Finding and wording never change anything;
`move_grill_preference` is the one place that writes, once, when a project still has a
`preferences.json`.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

from plan_review.paths.workdir import config_file, config_path, preferences_path
from plan_review.settings.prefs import GrillMode, save_grill_mode

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


def _read_object(path: Path) -> dict[str, Any] | None:
    """The JSON object in the file, or None when it can't be read or isn't an object."""
    try:
        loaded: Any = json.loads(path.read_bytes())
    except OSError, ValueError:
        return None
    return cast(dict[str, Any], loaded) if isinstance(loaded, dict) else None


@dataclass(frozen=True)
class _Outcome:
    """What to do about a `preferences.json`: the line to show, and whether to delete or save."""

    line: str | None
    delete: bool = False
    save: GrillMode | None = None  # a grill mode to write into the project's config.json


def _find_preferences(root: Path) -> tuple[Path, bool] | None:
    """The file to move and whether it is the old one in `.claude/`, or None if there is none."""
    kept = preferences_path(root)
    if kept.is_file():
        return kept, False
    old = root / _OLD_PREFERENCES
    return (old, True) if old.is_file() else None


def _decide(root: Path, path: Path, is_old: bool) -> _Outcome:
    """Read the file and the config, and say what to do. Changes nothing.

    Only the file in `.plan-review/work/` is ever deleted; the old one is left as it is."""
    name = path.relative_to(root).as_posix()
    prefs = _read_object(path)
    mode = None if prefs is None else prefs.get("grill")
    if prefs is None or mode not in (None, "page", "chat"):
        return _Outcome(f"plan-review: {name} can't be read and is ignored; delete it")
    if mode is None:
        if is_old:
            return _Outcome(None)  # nothing to say about a file we never touch
        return _Outcome(f"plan-review: {name} held no grill choice; deleted it", delete=True)
    source = config_source(root)
    settings = _read_object(source.path) if source.path.is_file() else {}
    if settings is None:
        return _Outcome(None)  # the reader reports the broken config
    target = config_path(root).relative_to(root).as_posix()
    if settings.get("grill") is not None:
        if is_old:
            return _Outcome(None)
        return _Outcome(
            f"plan-review: {target} already sets grill, so {name} was only deleted", delete=True
        )
    if is_old:
        line = f"plan-review: copied the grill choice ({mode}) from {name} into {target}"
    else:
        line = f"plan-review: moved the grill choice ({mode}) from {name} into {target}"
    return _Outcome(line, delete=not is_old, save=mode)


def _save_grill_choice(root: Path, mode: GrillMode) -> None:
    source = config_source(root)
    if source.path != config_path(root) and source.path.is_file():
        config_file(root).write_bytes(source.path.read_bytes())  # keep the old settings
    save_grill_mode(config_file(root), mode)


def move_grill_preference(root: Path) -> str | None:
    """Move the old `preferences.json` grill choice into the project's `config.json`, once.

    The file in `.plan-review/work/` is deleted after the move. The old one in `.claude/work/`
    is only copied and never changed. Returns the one line to show, None when there was nothing
    to do."""
    found = _find_preferences(root)
    if found is None:
        return None
    path, is_old = found
    outcome = _decide(root, path, is_old)
    if outcome.save is not None:
        _save_grill_choice(root, outcome.save)
    if outcome.delete:
        path.unlink()
    return outcome.line
