"""MarkdownAgents: the skill and agents as Markdown files with frontmatter."""

from pathlib import PurePosixPath

from plan_review.harness.agent_files import AGENT_SETTINGS, MarkdownAgents
from plan_review.harness.workflow import Workflow, WorkflowText
from plan_review.settings.pipeline_config import ModelChoice

NAMES = ("grill-explorer", "architect", "implementer", "test-reviewer", "code-reviewer")
MODELS = {
    "architect": ModelChoice(model="m-big", effort="e-high"),
    "implementer": ModelChoice(model="m-small"),
}


def sample_workflow() -> Workflow:
    return Workflow(
        ship=WorkflowText("ship", "Ship it", "# Ship {{arguments}}\n"),
        agents={n: WorkflowText(n, f"The {n}", "Rules: {{rules_file}}.\n") for n in NAMES},
    )


def test_markdown_agents_write_the_skill_and_agents_with_their_settings() -> None:
    files = MarkdownAgents(models=MODELS).files(
        sample_workflow(), {"arguments": "ARGS", "rules_file": "R.md"}
    )

    assert sorted(files) == sorted(
        [PurePosixPath("skills/ship/SKILL.md"), *(PurePosixPath(f"agents/{n}.md") for n in NAMES)]
    )
    ship = files[PurePosixPath("skills/ship/SKILL.md")]
    assert "disable-model-invocation: true\n---\n" in ship
    assert "# Ship ARGS" in ship
    architect = files[PurePosixPath("agents/architect.md")]
    assert "Rules: R.md." in architect


def test_claude_code_agent_frontmatter_takes_its_model_from_the_defaults() -> None:
    files = MarkdownAgents(models=MODELS).files(
        sample_workflow(), {"arguments": "ARGS", "rules_file": "R.md"}
    )

    architect = files[PurePosixPath("agents/architect.md")]
    assert "model: m-big\n" in architect
    assert "effort: e-high\n" in architect
    implementer = files[PurePosixPath("agents/implementer.md")]
    assert "model: m-small\n" in implementer
    assert "effort" not in implementer
    code_reviewer = files[PurePosixPath("agents/code-reviewer.md")]
    assert "model:" not in code_reviewer  # nothing set: the session's model


def test_agent_settings_hold_tools_only() -> None:
    assert set(AGENT_SETTINGS) == set(NAMES)
    assert all(set(vars(s)) == {"tools", "disallowed_tools"} for s in AGENT_SETTINGS.values())
    explorer = AGENT_SETTINGS["grill-explorer"]
    assert explorer.tools == "Read, Grep, Glob, Bash, Write"
    assert explorer.disallowed_tools == "Edit, NotebookEdit, Agent"
