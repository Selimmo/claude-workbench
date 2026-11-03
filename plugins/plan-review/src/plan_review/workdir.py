"""`.claude/work/`: each issue's plan, comments and reports, kept out of the project's git.

The folder ignores itself with its own `.gitignore`, so a project needs no setup.
"""

from pathlib import Path


def work_dir(root: Path, issue: int) -> Path:
    """`.claude/work/<issue>/` under the project root `root`."""
    return root / ".claude" / "work" / str(issue)


def ensure_work_dir(root: Path, issue: int) -> Path:
    """Create `.claude/work/<issue>/` under the project root `root`, and return it."""
    work = work_dir(root, issue)
    work.mkdir(parents=True, exist_ok=True)
    ignore = work.parent / ".gitignore"
    if not ignore.exists():  # never overwrite a project's own rules
        ignore.write_text("*\n")
    return work
