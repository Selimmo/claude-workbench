"""Where the user's own plan-review folder is."""

import os
import sys
from collections.abc import Callable, Mapping
from pathlib import Path


def user_config_dir(
    platform: str = sys.platform,
    environ: Mapping[str, str] = os.environ,
    home: Callable[[], Path] = Path.home,
) -> Path:
    """The Windows folder is under `%APPDATA%` (or `~\\AppData\\Roaming`); else `~/.plan-review`."""
    if platform == "win32":
        appdata = environ.get("APPDATA")
        base = Path(appdata) if appdata else home() / "AppData" / "Roaming"
        return base / "plan-review"
    return home() / ".plan-review"
