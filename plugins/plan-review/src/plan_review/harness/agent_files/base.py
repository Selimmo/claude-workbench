"""The AgentFiles protocol, apart from its implementations so they can import it."""

from collections.abc import Mapping
from pathlib import PurePosixPath
from typing import Protocol

from plan_review.harness.workflow import Workflow


class AgentFiles(Protocol):
    """A file format for the ship skill and the agents."""

    def files(self, workflow: Workflow, slots: Mapping[str, str]) -> dict[PurePosixPath, str]:
        """Which files, where, and what they hold, with every `{{slot}}` filled in."""
        ...
