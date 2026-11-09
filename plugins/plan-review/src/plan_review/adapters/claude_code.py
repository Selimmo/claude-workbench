"""Everything specific to Claude Code.

Claude Code keeps a copy of each installed version and only fetches a new one when the
marketplace offers a new version, so an upgrade is: refresh the marketplace, then update.
"""

import shutil
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from plan_review.workflow import Workflow, fill

MARKETPLACE = "claude-workbench"
STEPS = [
    ["plugin", "marketplace", "update", MARKETPLACE],
    ["plugin", "update", f"plan-review@{MARKETPLACE}"],
]


SHIP_HEADER = {
    "argument-hint": "<issue number, issue link or prompt> [--grill[=page|chat]]",
    "disable-model-invocation": "true",
}

# The text the workflow leaves to the CLI.
SLOTS: Mapping[str, str] = {
    "arguments": "$ARGUMENTS",
    "agent_prefix": "plan-review:",
    "agent_override": ".claude/agents/<name>.md",
    "rules_file": "CLAUDE.md",
    "harness_folder": ".claude/",
    "skill_tool": "with the Skill tool",
    "background": "with the Bash tool in the background (`run_in_background`)",
    "event_source": (
        "with the **Monitor** tool's WebSocket source: "
        "`ws://127.0.0.1:<port>/events`, `timeout_ms: 1800000`, description"
    ),
    "watcher": "Monitor",
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


class ClaudeCode:
    name = "Claude Code"
    slots = SLOTS
    agent_settings = AGENT_SETTINGS

    def installed_at(self, package_root: Path) -> bool:
        return (package_root / ".claude-plugin" / "plugin.json").is_file()

    def available(self) -> bool:
        return shutil.which("claude") is not None

    def upgrade(self) -> int:
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

    def upgrade_commands(self) -> list[str]:
        return [" ".join(["claude", *step]) for step in STEPS]

    def files(self, workflow: Workflow) -> dict[PurePosixPath, str]:
        ship = workflow.ship
        files = {
            PurePosixPath("skills/ship/SKILL.md"): _frontmatter(
                {"name": ship.name, "description": ship.description, **SHIP_HEADER}
            )
            + fill(ship.body, self.slots)
        }
        for name, agent in workflow.agents.items():
            settings = self.agent_settings[name]
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
                agent.body, self.slots
            )
        return files
