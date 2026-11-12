"""Everything specific to Claude Code.

Claude Code keeps a copy of each installed version and only fetches a new one when the
marketplace offers a new version, so an upgrade is: refresh the marketplace, then update.
"""

from plan_review.harness.agent_files import MarkdownAgents
from plan_review.harness.distribution import MarketplacePlugin
from plan_review.harness.harness import Harness
from plan_review.harness.waiting import SocketWaiting
from plan_review.harness.wording import Wording

MARKETPLACE = "claude-workbench"

KEY = "claude-code"
NAME = "Claude Code"

HARNESS = Harness(
    key=KEY,
    name=NAME,
    wording=Wording(
        arguments="$ARGUMENTS",
        agent_prefix="plan-review:",
        agent_override=".claude/agents/<name>.md",
        rules_file="CLAUDE.md",
        rules_also=" (or `AGENTS.md`)",
        harness_folder=".claude/",
        skill_tool="with the Skill tool",
    ),
    agent_files=MarkdownAgents(),
    distribution=MarketplacePlugin(
        tool_name=NAME,
        program="claude",
        marketplace=MARKETPLACE,
        plugin="plan-review",
        marker=".claude-plugin/plugin.json",
        after_upgrade="Run /reload-plugins in a running session, or start a new one, to use it.",
    ),
    waiting=SocketWaiting(listener="Monitor"),
)
