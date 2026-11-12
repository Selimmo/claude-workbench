"""One file per tool that can run the agents, each holding one `HARNESS` value.

Every module in this folder is a tool, found each time it is asked for, in file-name order.
That order is the order of the checks in `installed_adapter`: the first tool that recognises
the folder wins, so `claude_code.py` sorts before `codex.py` on purpose. Keep only tool files
here; shared code belongs in the piece folders next to this one.
"""

import importlib
import pkgutil
from pathlib import Path

from plan_review.harness.harness import Harness


def all_adapters() -> list[Harness]:
    """The harness of every tool file in this folder, in file-name order."""
    names = sorted(module.name for module in pkgutil.iter_modules(__path__))
    return [importlib.import_module(f"{__name__}.{name}").HARNESS for name in names]


def installed_adapter(package_root: Path) -> Harness | None:
    """The tool that installed the copy of plan-review in `package_root`, if any."""
    return next((h for h in all_adapters() if h.distribution.installed_at(package_root)), None)


def adapter_by_key(key: str) -> Harness | None:
    return next((h for h in all_adapters() if h.key == key), None)
