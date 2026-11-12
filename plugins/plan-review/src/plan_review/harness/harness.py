"""What the core knows about a CLI that runs the agents: which pieces it uses."""

from dataclasses import asdict, dataclass
from pathlib import PurePosixPath

from plan_review.harness.agent_files import AgentFiles
from plan_review.harness.distribution import SelfInstall, ToolInstall
from plan_review.harness.waiting import WAITING_TEXTS, WaitingStyle
from plan_review.harness.wording import Wording
from plan_review.harness.workflow import Workflow


@dataclass(frozen=True)
class Harness:
    """Which pieces a tool uses, and nothing else of its own."""

    key: str
    name: str
    wording: Wording
    agent_files: AgentFiles
    distribution: SelfInstall | ToolInstall
    waiting: WaitingStyle

    def slots(self) -> dict[str, str]:
        """The Wording fields plus the waiting texts: the `{{slot}}` values the workflow needs."""
        waiting = {name: getattr(self.waiting, name) for name in WAITING_TEXTS}
        return {**asdict(self.wording), **waiting}

    def files(self, workflow: Workflow) -> dict[PurePosixPath, str]:
        return self.agent_files.files(workflow, self.slots())

    def install(self) -> int:
        """A tool plan-review installs itself is installed; any other prints how, and exits 2."""
        if isinstance(self.distribution, SelfInstall):
            return self.distribution.install()
        print(self.distribution.install_hint())
        return 2
