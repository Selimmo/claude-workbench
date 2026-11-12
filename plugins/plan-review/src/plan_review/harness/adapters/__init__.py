"""One file per tool that can run the agents, each holding one `HARNESS` value.

Every module in this folder is a tool, found each time it is asked for, in file-name order.
Several tools can recognise one copy of plan-review (each by its own files), and upgrade runs
every one that does; the file-name order only fixes the order they run in, it picks no winner.
Keep only tool files here; shared code belongs in the piece folders next to this one.
"""

import importlib
import pkgutil
from pathlib import Path

from plan_review.harness.harness import Harness


def all_adapters() -> list[Harness]:
    """The harness of every tool file in this folder, in file-name order."""
    names = sorted(module.name for module in pkgutil.iter_modules(__path__))
    return [importlib.import_module(f"{__name__}.{name}").HARNESS for name in names]


def installed_adapters(package_root: Path) -> list[Harness]:
    """Every tool that recognises the copy of plan-review in `package_root`."""
    return [h for h in all_adapters() if h.distribution.installed_at(package_root)]


def adapter_by_key(key: str) -> Harness | None:
    return next((h for h in all_adapters() if h.key == key), None)
