"""`plan-review upgrade`: hand over to the distribution of the CLI that installed this copy.

When it can't tell which that is, or the CLI is missing, it changes nothing and prints
what to run instead.
"""

import sys
from pathlib import Path

from plan_review.harness.adapters import all_adapters, installed_adapter
from plan_review.harness.distribution import ToolInstall

# In an install this is the plugin folder, because uv installs the plugin editable.
PACKAGE_ROOT = Path(__file__).parents[3]


def _print_commands(heading: str) -> None:
    print(heading, file=sys.stderr)
    for harness in all_adapters():
        print(f"  {harness.name}:", file=sys.stderr)
        for command in harness.distribution.upgrade_commands():
            print(f"    {command}", file=sys.stderr)


def upgrade() -> int:
    harness = installed_adapter(PACKAGE_ROOT)
    if harness is None:
        _print_commands("plan-review can't tell how it was installed. To upgrade, run:")
        return 1
    distribution = harness.distribution
    if isinstance(distribution, ToolInstall) and not distribution.available():
        print(f"{harness.name} was not found on PATH: install it first.", file=sys.stderr)
        _print_commands("Then run:")
        return 1
    return distribution.upgrade()
