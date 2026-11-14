"""TomlAgents: the skill and agents as marked files inside one folder, agents as TOML."""

import tomllib
from pathlib import PurePosixPath

from plan_review.harness.agent_files import TomlAgents
from plan_review.harness.workflow import Workflow, WorkflowText

NAMES = ("grill-explorer", "architect", "implementer", "test-reviewer", "code-reviewer")


def test_toml_agents_write_marked_files_inside_their_folder() -> None:
    workflow = Workflow(
        ship=WorkflowText("ship", "Ship it", "# Ship\n"),
        agents={n: WorkflowText(n, f"The {n}", "Rules: {{rules_file}}.\n") for n in NAMES},
    )
    agents = TomlAgents(
        folder=PurePosixPath("x"), mark="MARK-x", extra_files={PurePosixPath("a.yaml"): "y"}
    )

    files = agents.files(workflow, {"rules_file": "R.md", "agent_prefix": "plan-review-"})

    root = PurePosixPath("x")
    assert sorted(files) == sorted(
        [
            root / "skills/ship/SKILL.md",
            root / "a.yaml",
            *(root / f"agents/plan-review-{n}.toml" for n in NAMES),
        ]
    )
    assert files[root / "a.yaml"] == "y"
    for path, text in files.items():
        if path.name != "a.yaml":
            assert "MARK-x" in text
    data = tomllib.loads(files[root / "agents/plan-review-architect.toml"])
    assert data["name"] == "plan-review-architect"
    assert data["developer_instructions"] == "Rules: R.md.\n"


def test_toml_agent_names_use_the_agent_prefix_slot() -> None:
    workflow = Workflow(
        ship=WorkflowText("ship", "Ship it", "# Ship\n"),
        agents={"architect": WorkflowText("architect", "The architect", "Body\n")},
    )
    agents = TomlAgents(folder=PurePosixPath("x"), mark="MARK-x", extra_files={})

    files = agents.files(workflow, {"agent_prefix": "sample-"})

    data = tomllib.loads(files[PurePosixPath("x/agents/sample-architect.toml")])
    assert data["name"] == "sample-architect"
