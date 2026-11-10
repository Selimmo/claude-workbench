"""How a tool gets plan-review installed and upgraded, split by what the tool can do."""

from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class Distribution(Protocol):
    def installed_at(self, package_root: Path) -> bool:
        """Is this copy of plan-review installed this way?"""
        ...

    def upgrade(self) -> int:
        """Update the installed copy; the exit code."""
        ...

    def upgrade_commands(self) -> list[str]:
        """What a person would run, for when plan-review can't do it itself."""
        ...


@runtime_checkable
class SelfInstall(Distribution, Protocol):
    """plan-review can put this tool's files in place itself."""

    def install(self) -> int:
        """Write the files where the tool reads them; the exit code."""
        ...


@runtime_checkable
class ToolInstall(Distribution, Protocol):
    """The tool's own program installs plan-review, so plan-review only says how."""

    def available(self) -> bool:
        """Is the tool's program on this machine?"""
        ...

    def install_hint(self) -> str:
        """The command that installs plan-review through the tool."""
        ...
