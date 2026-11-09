"""What the core knows about a CLI that runs the agents: this protocol, and nothing else."""

from pathlib import Path, PurePosixPath
from typing import Protocol

from plan_review.workflow import Workflow


class Adapter(Protocol):
    """Everything specific to one CLI that runs the agents."""

    name: str

    def installed_at(self, package_root: Path) -> bool:
        """Is this copy of plan-review installed through this CLI?"""
        ...

    def available(self) -> bool:
        """Is the CLI itself on this machine?"""
        ...

    def upgrade(self) -> int:
        """Update the installed plugin through the CLI; the exit code."""
        ...

    def upgrade_commands(self) -> list[str]:
        """What a person would run, for when plan-review can't do it itself."""
        ...

    def files(self, workflow: Workflow) -> dict[PurePosixPath, str]:
        """Which files this CLI needs, where, and what they hold."""
        ...
