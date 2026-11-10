"""MarkdownAgents: the skill and agents as Markdown files with frontmatter."""

from pathlib import PurePosixPath

from plan_review.harness.agent_files import MarkdownAgents
from plan_review.harness.workflow import Workflow, WorkflowText

NAMES = ("architect", "implementer", "test-reviewer", "code-reviewer")


def sample_workflow() -> Workflow:
    return Workflow(
        ship=WorkflowText("ship", "Ship it", "# Ship {{arguments}}\n"),
        agents={n: WorkflowText(n, f"The {n}", "Rules: {{rules_file}}.\n") for n in NAMES},
    )


def test_markdown_agents_write_the_skill_and_agents_with_their_settings() -> None:
    files = MarkdownAgents().files(sample_workflow(), {"arguments": "ARGS", "rules_file": "R.md"})

    assert sorted(files) == sorted(
        [PurePosixPath("skills/ship/SKILL.md"), *(PurePosixPath(f"agents/{n}.md") for n in NAMES)]
    )
    ship = files[PurePosixPath("skills/ship/SKILL.md")]
    assert "disable-model-invocation: true\n---\n" in ship
    assert "# Ship ARGS" in ship
    architect = files[PurePosixPath("agents/architect.md")]
    assert "model: opus\n" in architect
    assert "effort: high\n" in architect
    assert "Rules: R.md." in architect
    assert "effort" not in files[PurePosixPath("agents/implementer.md")]
