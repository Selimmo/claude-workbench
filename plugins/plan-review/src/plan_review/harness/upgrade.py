"""`plan-review upgrade`: hand over to the adapter of the CLI that installed this copy.

When it can't tell which that is, or the CLI is missing, it changes nothing and prints
what to run instead.
"""

import sys
from pathlib import Path

from plan_review.harness.adapters import ADAPTERS, installed_adapter

# In an install this is the plugin folder, because uv installs the plugin editable.
PACKAGE_ROOT = Path(__file__).parents[3]


def _print_commands(heading: str) -> None:
    print(heading, file=sys.stderr)
    for adapter in ADAPTERS:
        print(f"  {adapter.name}:", file=sys.stderr)
        for command in adapter.upgrade_commands():
            print(f"    {command}", file=sys.stderr)


def upgrade() -> int:
    adapter = installed_adapter(PACKAGE_ROOT)
    if adapter is None:
        _print_commands("plan-review can't tell how it was installed. To upgrade, run:")
        return 1
    if not adapter.available():
        print(f"{adapter.name} was not found on PATH: install it first.", file=sys.stderr)
        _print_commands("Then run:")
        return 1
    return adapter.upgrade()
