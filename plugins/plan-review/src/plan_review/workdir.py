"""`.claude/work/`: each run's plan, comments and reports, kept out of the project's git.

A run is keyed by a run id (see `run_id`): an issue key, or a dated prompt name.
The folder ignores itself with its own `.gitignore`, so a project needs no setup.
"""

from datetime import date
from itertools import count
from pathlib import Path


def work_dir(root: Path, run_id: str) -> Path:
    """`.claude/work/<run_id>/` under the project root `root`."""
    return root / ".claude" / "work" / run_id


def ensure_work_dir(root: Path, run_id: str) -> Path:
    """Create `.claude/work/<run_id>/` under the project root `root`, and return it."""
    work = work_dir(root, run_id)
    work.mkdir(parents=True, exist_ok=True)
    _ignore_work_folder(work.parent)
    return work


def preferences_path(root: Path) -> Path:
    """Where `.claude/work/preferences.json` is, without creating anything."""
    return root / ".claude" / "work" / "preferences.json"


def preferences_file(root: Path) -> Path:
    """`.claude/work/preferences.json`, with the folder and its `.gitignore` in place."""
    folder = root / ".claude" / "work"
    folder.mkdir(parents=True, exist_ok=True)
    _ignore_work_folder(folder)
    return preferences_path(root)


def new_prompt_work_dir(root: Path, name: str, today: date) -> Path:
    """A new folder `<name>-<date>`, or `<name>-<date>-2`, `-3`, ... when that one exists."""
    base = f"{name}-{today.isoformat()}"
    for attempt in count(1):
        work = work_dir(root, base if attempt == 1 else f"{base}-{attempt}")
        work.parent.mkdir(parents=True, exist_ok=True)
        try:
            work.mkdir()
        except FileExistsError:
            continue
        _ignore_work_folder(work.parent)
        return work
    raise AssertionError("unreachable")  # pragma: no cover


def _ignore_work_folder(folder: Path) -> None:
    ignore = folder / ".gitignore"
    if not ignore.exists():  # never overwrite a project's own rules
        ignore.write_text("*\n")
