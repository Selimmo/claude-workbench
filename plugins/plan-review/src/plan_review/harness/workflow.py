"""The /ship workflow and the five agents, as written once in `workflow/`.

The text is tied to no CLI: where a CLI needs its own words, it holds a `{{slot}}` that
the CLI's adapter fills in.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

AGENT_NAMES = ("grill-explorer", "architect", "implementer", "test-reviewer", "code-reviewer")
_SLOT = re.compile(r"\{\{(\w+)\}\}")


@dataclass(frozen=True)
class WorkflowText:
    """One text in workflow/: the /ship workflow or an agent."""

    name: str
    description: str
    body: str


@dataclass(frozen=True)
class Workflow:
    """The text in workflow/, as read from disk."""

    ship: WorkflowText
    agents: dict[str, WorkflowText]


def _read(path: Path) -> WorkflowText:
    _, header, body = path.read_text(encoding="utf-8").split("---\n", 2)
    pairs = (line.split(":", 1) for line in header.splitlines())
    meta = {key.strip(): value.strip() for key, value in pairs}
    return WorkflowText(meta["name"], meta["description"], body)


def load_workflow(folder: Path) -> Workflow:
    return Workflow(
        ship=_read(folder / "ship.md"),
        agents={name: _read(folder / "agents" / f"{name}.md") for name in AGENT_NAMES},
    )


def fill(template: str, slots: Mapping[str, str]) -> str:
    """Replace each `{{slot}}`. A slot with no value is an error, so a typo can't ship."""

    def value(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in slots:
            raise ValueError(f"no value for the slot '{{{{{name}}}}}'")
        return slots[name]

    return _SLOT.sub(value, template)
