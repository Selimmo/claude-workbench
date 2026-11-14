"""The project root, found from any folder inside the project.

Every command reads `.plan-review/` from here, so running one from a subfolder sees the same
settings and run folders as running it from the top.
"""

from pathlib import Path


def project_root(start: Path, user_dir: Path) -> Path:
    """The nearest folder from `start` upwards that has `.plan-review/`, not above the git root.

    Without one, the git root (the nearest folder with `.git`). Outside git, `start` itself:
    there is nothing to bound the search, so nothing above it is read. `user_dir` is the owner's
    own settings folder (`~/.plan-review`), which never makes its parent a project.
    """
    start = start.resolve()
    user = user_dir.resolve()
    git_root = next((p for p in (start, *start.parents) if (p / ".git").exists()), None)
    if git_root is None:
        return start
    for folder in (start, *start.parents):
        marker = folder / ".plan-review"
        if marker.is_dir() and marker.resolve() != user:
            return folder
        if folder == git_root:
            break
    return git_root
