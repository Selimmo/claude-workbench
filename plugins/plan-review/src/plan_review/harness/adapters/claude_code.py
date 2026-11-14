"""Everything specific to Claude Code.

Claude Code keeps a copy of each installed version and only fetches a new one when the
marketplace offers a new version, so an upgrade is: refresh the marketplace, then update.
"""

from pathlib import Path, PurePosixPath

from plan_review.harness.agent_files import MarkdownAgents
from plan_review.harness.distribution import MarketplacePlugin
from plan_review.harness.harness import Harness
from plan_review.harness.waiting import SocketWaiting
from plan_review.harness.wording import Wording
from plan_review.settings.agent_rules import AgentRules
from plan_review.settings.pipeline_config import ModelChoice

MARKETPLACE = "claude-workbench"

KEY = "claude-code"
NAME = "Claude Code"

PLUGIN_ROOT = Path(__file__).parents[4]  # the plugin folder, with agents/ in it
PREFIX = "plan-review:"
_OPUS = ModelChoice(model="opus", effort="high")

RULES = AgentRules(
    own_prefix=PREFIX,
    defaults={
        "grill-explorer": _OPUS,
        "architect": _OPUS,
        "implementer": ModelChoice(model="sonnet"),
        "test-reviewer": _OPUS,
        "code-reviewer": _OPUS,
    },
    models=frozenset({"opus", "sonnet", "haiku", "fable"}),
    efforts=frozenset({"low", "medium", "high", "xhigh", "max"}),
    project_agent_folders=(PurePosixPath(".claude/agents"),),
    user_agent_folders=lambda: (Path.home() / ".claude" / "agents",),
    agent_suffix=".md",
    own_agent_file=lambda role: PLUGIN_ROOT / "agents" / f"{role}.md",
)


HARNESS = Harness(
    key=KEY,
    name=NAME,
    wording=Wording(
        arguments="$ARGUMENTS",
        agent_prefix=PREFIX,
        agent_override=".claude/agents/<name>.md` in the project, or `~/.claude/agents/<name>.md",
        rules_file="CLAUDE.md",
        rules_also=" (or `AGENTS.md`)",
        harness_folder=".claude/",
        start_agent=(
            "with the Agent tool: `subagent_type` is the `agent` value, `model` is the `model` "
            "value and `effort` is the `effort` value."
        ),
        start_together=(
            "one Agent call per reviewer, all in the same message; wait until every one has "
            "returned"
        ),
        unknown_agent=(
            "tell the owner the agent file is missing (`launch` printed its name) and stop."
        ),
    ),
    agent_files=MarkdownAgents(models=RULES.defaults),
    distribution=MarketplacePlugin(
        tool_name=NAME,
        program="claude",
        marketplace=MARKETPLACE,
        plugin="plan-review",
        marker=".claude-plugin/plugin.json",
        after_upgrade="Run /reload-plugins in a running session, or start a new one, to use it.",
    ),
    waiting=SocketWaiting(listener="Monitor"),
    rules=RULES,
)
