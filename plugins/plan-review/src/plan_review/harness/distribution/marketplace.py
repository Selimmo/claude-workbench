"""A plugin installed and updated by the tool's own program, from a marketplace."""

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MarketplacePlugin:
    """The tool keeps a copy of each installed version and only fetches a new one when the
    marketplace offers a new version, so an upgrade is: refresh the marketplace, then update.

    `marker` is a file, relative to the plugin folder, that only this tool's copy has.
    `after_upgrade` is told to the owner once the update has run.
    """

    tool_name: str
    program: str
    marketplace: str
    plugin: str
    marker: str
    after_upgrade: str

    def _steps(self) -> list[list[str]]:
        return [
            ["plugin", "marketplace", "update", self.marketplace],
            ["plugin", "update", f"{self.plugin}@{self.marketplace}"],
        ]

    def installed_at(self, package_root: Path) -> bool:
        return (package_root / self.marker).is_file()

    def available(self) -> bool:
        return shutil.which(self.program) is not None

    def upgrade(self) -> int:
        program = shutil.which(self.program)
        if program is None:
            print(
                f"`{self.program}` not found on PATH: install {self.tool_name} first",
                file=sys.stderr,
            )
            return 1
        for step in self._steps():
            code = subprocess.run([program, *step], check=False).returncode
            if code != 0:
                return code
        print(self.after_upgrade)
        return 0

    def upgrade_commands(self) -> list[str]:
        return [" ".join([self.program, *step]) for step in self._steps()]

    def install_hint(self) -> str:
        return (
            f"{self.tool_name} installs plan-review as a plugin: "
            f"`{self.program} plugin install {self.plugin}@{self.marketplace}`"
        )
