"""`plan-review upgrade`: hand over to the distribution of each CLI that installed this copy.

When it can't tell which that is, or the CLI is missing, it changes nothing and prints
what to run instead.
"""

import sys
from pathlib import Path

from plan_review.harness.adapters import all_adapters, installed_adapters
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
    """Upgrade every tool that recognises this copy, in order; stop at the first failure."""
    harnesses = installed_adapters(PACKAGE_ROOT)
    if not harnesses:
        _print_commands("plan-review can't tell how it was installed. To upgrade, run:")
        return 1
    for harness in harnesses:
        distribution = harness.distribution
        if isinstance(distribution, ToolInstall) and not distribution.available():
            print(f"{harness.name} was not found on PATH: install it first.", file=sys.stderr)
            _print_commands("Then run:")
            return 1
        code = distribution.upgrade()
        if code != 0:
            return code
    return 0
