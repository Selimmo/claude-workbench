"""Markdown files with a frontmatter header: one skill and one file per agent."""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import ClassVar

from plan_review.harness.workflow import Workflow, fill

SHIP_HEADER = {
    "argument-hint": "<issue number, issue link or prompt> [--grill[=page|chat]]",
    "disable-model-invocation": "true",
}


@dataclass(frozen=True)
class AgentSettings:
    tools: str
    disallowed_tools: str
    model: str
    effort: str | None = None


# Models by nickname only, so a new release needs no change here.
AGENT_SETTINGS: Mapping[str, AgentSettings] = {
    "architect": AgentSettings(
        "Read, Grep, Glob, Bash, Write", "Edit, NotebookEdit, Agent", "opus", "high"
    ),
    "implementer": AgentSettings("Read, Grep, Glob, Bash, Write, Edit", "Agent", "sonnet"),
    "test-reviewer": AgentSettings(
        "Read, Grep, Glob, Bash", "Write, Edit, NotebookEdit, Agent", "opus", "high"
    ),
    "code-reviewer": AgentSettings(
        "Read, Grep, Glob, Bash", "Write, Edit, NotebookEdit, Agent", "opus", "high"
    ),
}


def _frontmatter(fields: Mapping[str, str]) -> str:
    return "---\n" + "".join(f"{key}: {value}\n" for key, value in fields.items()) + "---\n"


@dataclass(frozen=True)
class MarkdownAgents:
    settings: ClassVar[Mapping[str, AgentSettings]] = AGENT_SETTINGS

    def files(self, workflow: Workflow, slots: Mapping[str, str]) -> dict[PurePosixPath, str]:
        ship = workflow.ship
        files = {
            PurePosixPath("skills/ship/SKILL.md"): _frontmatter(
                {"name": ship.name, "description": ship.description, **SHIP_HEADER}
            )
            + fill(ship.body, slots)
        }
        for name, agent in workflow.agents.items():
            settings = self.settings[name]
            fields = {
                "name": agent.name,
                "description": agent.description,
                "tools": settings.tools,
                "disallowedTools": settings.disallowed_tools,
                "model": settings.model,
            }
            if settings.effort is not None:
                fields["effort"] = settings.effort
            files[PurePosixPath(f"agents/{name}.md")] = _frontmatter(fields) + fill(
                agent.body, slots
            )
        return files
