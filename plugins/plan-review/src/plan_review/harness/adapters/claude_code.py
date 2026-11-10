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

from plan_review.harness.workflow import Workflow, fill

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
    "rules_also": " (or `AGENTS.md`)",
    "start_viewer": (
        "Start `plan-review serve ID` with the Bash tool in the background (`run_in_background`)."
    ),
    "start_viewer_inline": (
        "start `plan-review serve ID` with the Bash tool in the background (`run_in_background`)"
    ),
    "resume_viewer": "start `plan-review serve ID` as in point 2",
    "ignore_repeat": "ignore it.",
    "viewer_output": (
        "Read its first output line, `plan-review: <label> at http://127.0.0.1:<port>/`, "
        "from the task's output file, and give the owner that URL."
    ),
    "viewer_kept": (
        "do not start another (point 1) or arm a second Monitor (point 2): "
        "the same Monitor receives the review events too."
    ),
    "keep_viewer": "Keep the server and the Monitor running: step 3 reuses them.",
    "stop_viewer": "stop the Monitor and the server task",
    "abort_viewer": "stop the Monitor and the server",
    "grill_listen": (
        "Subscribe with the **Monitor** tool's WebSocket source: "
        "`ws://127.0.0.1:<port>/events`, `timeout_ms: 1800000`, description "
        "`plan-review <label> grill`. When it expires, arm it again and catch up with "
        "`plan-review grill pending ID`, because events sent while no Monitor listens are "
        "lost: handle every pending owner action as below."
    ),
    "review_listen": (
        "Subscribe to the owner's actions with the **Monitor** tool's WebSocket source: "
        "`ws://127.0.0.1:<port>/events`, `timeout_ms: 1800000`, description "
        "`plan-review <label>`. A Monitor lasts at most 30 minutes: when it expires before "
        "`approved`, arm it again. Events sent while no Monitor is listening are not replayed "
        "(the viewer keeps the last one only so the owner can press Resend), so each time you "
        "arm it again, catch up: run `plan-review threads ID` and treat every thread whose last "
        "message is the owner's (no reply from you yet) as part of a review, and handle it as "
        "below; if `W/approved.json` exists, the plan was approved: handle it as `approved` "
        "below."
    ),
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
    key = "claude-code"
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

    def install(self) -> int:
        print(
            "Claude Code installs plan-review as a plugin: "
            f"`claude plugin install plan-review@{MARKETPLACE}`"
        )
        return 2

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
