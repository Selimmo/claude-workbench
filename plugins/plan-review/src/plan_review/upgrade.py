"""`plan-review upgrade`: update the installed plugin through Claude Code's own CLI.

Claude Code keeps a copy of each installed version and only fetches a new one when the
marketplace offers a new version, so an upgrade is: refresh the marketplace, then update.
"""

import shutil
import subprocess
import sys

MARKETPLACE = "claude-workbench"
STEPS = [
    ["plugin", "marketplace", "update", MARKETPLACE],
    ["plugin", "update", f"plan-review@{MARKETPLACE}"],
]


def upgrade() -> int:
    claude = shutil.which("claude")
    if claude is None:
        print("`claude` not found on PATH: install Claude Code first", file=sys.stderr)
        return 1
    for step in STEPS:
        code = subprocess.run([claude, *step], check=False).returncode
        if code != 0:
            return code
    print("Run /reload-plugins in a running session, or start a new one, to use it.")
    return 0
