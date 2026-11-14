"""The agents and steps of a run, and the rules for a workflow."""

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Any, Literal

REQUIRED_AGENTS = ("grill-explorer", "architect")
OPTIONAL_AGENTS = ("implementer", "test-reviewer", "code-reviewer")
# The required steps around the workflow, by the names the README uses.
FIXED_STEPS = ("grill", "plan", "review", "branch", "hand-back")
BUILT_IN_WORKFLOW = ("implementer", "test-reviewer", "code-reviewer")


def step_problems(where: str, workflow: Sequence[str | Sequence[str]]) -> list[str]:
    """One line per broken rule, each starting with `where`."""
    problems: list[str] = []
    seen: set[str] = set()
    for position, item in enumerate(workflow):
        group = [item] if isinstance(item, str) else list(item)
        for name in group:
            problems.extend(_step_problem(where, name, not isinstance(item, str), position, seen))
            seen.add(name)
    return problems


def _step_problem(where: str, name: str, grouped: bool, position: int, seen: set[str]) -> list[str]:
    if name in REQUIRED_AGENTS:
        return [f"{where}: {name} is required and always runs before the workflow; leave it out"]
    if name in FIXED_STEPS:
        return [f"{where}: {name} always runs; leave it out"]
    if name in seen:
        return [f"{where}: {name} is listed twice"]
    if name == "implementer" and grouped:
        return [
            f"{where}: the implementer can't be in a group: "
            "nothing runs at the same time as the implementer"
        ]
    if name == "implementer" and position > 0:
        return [
            f"{where}: the implementer would come after {', '.join(sorted(seen))}, "
            f"which would review code that isn't written yet: the implementer comes first"
        ]
    return []


def review_file(name: str) -> str:
    """The file in the run's folder where a reviewer's review is kept."""
    return {"test-reviewer": "test-review.md", "code-reviewer": "code-review.md"}.get(
        name, f"review-{name}.md"
    )


@dataclass(frozen=True)
class AgentStart:
    """How to start one agent now."""

    name: str  # the role or custom name from the config
    kind: Literal["grill-explorer", "architect", "implementer", "reviewer"]
    agent: str | None  # what to start; None: the main session does it
    model: str | None  # None: the session's
    effort: str | None
    review: str | None = None  # for a reviewer: its review file in the run's folder
    main_session: bool = False
    instructions: str | None = None  # for the main session: the instructions to follow

    def to_json(self) -> dict[str, Any]:
        """What `plan-review launch` prints."""
        return asdict(self)
