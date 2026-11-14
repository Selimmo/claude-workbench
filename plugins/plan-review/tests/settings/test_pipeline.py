"""The settings file as one tool's config: every field, and what a bad one says."""

import json
from pathlib import Path

import pytest

from plan_review.harness.adapters import all_adapters
from plan_review.settings.agent_rules import AgentRules
from plan_review.settings.pipeline_config import PipelineConfig, PipelineConfigError
from plan_review.settings.reader import ConfigReader

EXAMPLE = Path(__file__).parents[2] / "examples" / "config.json"
RULES = {h.key: h.rules for h in all_adapters()}


def load(tmp_path: Path, config: object, rules: dict[str, AgentRules] = RULES) -> PipelineConfig:
    """The settings in force for a project whose config.json holds `config`."""
    root = tmp_path / "project"
    (root / ".plan-review").mkdir(parents=True, exist_ok=True)
    (root / ".plan-review" / "config.json").write_text(json.dumps(config))
    return ConfigReader.load(root, tmp_path / "user", rules).config


def test_missing_file_gives_the_defaults(tmp_path: Path) -> None:
    config = ConfigReader.load(tmp_path, tmp_path / "user", RULES).config

    assert config.checks == []
    assert config.review_rules == []
    assert config.branch == "{issue}-{slug}"
    assert config.viewer.open == "browser"
    assert config.max_review_rounds == 3
    assert config.tdd is True
    assert config.mutation is None
    assert config.agents == {}
    assert config.harness == {}


def test_project_values_are_read(tmp_path: Path) -> None:
    config = load(
        tmp_path,
        {
            "checks": [{"name": "backend", "run": "backend/check.sh"}],
            "review_rules": ["Provider formats stay in backend/providers/"],
            "branch": "{issue}-{slug}",
            "viewer": {"open": "none"},
            "max_review_rounds": 2,
        },
    )

    assert config.checks[0].run == "backend/check.sh"
    assert config.viewer.open == "none"
    assert config.max_review_rounds == 2


@pytest.mark.parametrize(
    ("config", "error"),
    [
        ({"chekcs": []}, "chekcs: Extra inputs are not permitted"),
        ({"viewer": {"open": "tab"}}, "viewer.open: Input should be 'browser' or 'none'"),
        ({"branch": "feature-{slug}"}, "branch: must contain {issue}"),
        ({"max_review_rounds": 0}, "max_review_rounds: Input should be greater than or equal to 1"),
        ({"mutation": ""}, "mutation: String should have at least 1 character"),
        ({"tdd": "sometimes"}, "tdd: Input should be a valid boolean"),
        ({"agents": {"x": {"kind": "writer"}}}, "agents.x.kind: Input should be 'reviewer'"),
        (
            {"harness": {"claude-code": {"architect": {"modle": "x"}}}},
            "harness.claude-code.architect.modle: Extra inputs are not permitted",
        ),
    ],
)
def test_bad_config_is_reported_readably(tmp_path: Path, config: object, error: str) -> None:
    with pytest.raises(PipelineConfigError) as raised:
        load(tmp_path, config)

    assert error in raised.value.errors[0]


def test_the_example_config_is_valid_for_every_tool_and_sets_every_field(tmp_path: Path) -> None:
    example = json.loads(EXAMPLE.read_text())
    root = tmp_path / "project"
    for rules in RULES.values():  # the agent files the example names
        folder = root / rules.project_agent_folders[0]
        folder.mkdir(parents=True)
        for name in ("security-reviewer", "code-reviewer"):
            (folder / f"{name}{rules.agent_suffix}").write_text("mine")

    config = load(tmp_path, example)

    assert config.model_fields_set == set(PipelineConfig.model_fields)
    reader = ConfigReader.load(root, tmp_path / "user", RULES)
    assert {tool: reader.problems(tool) for tool in RULES} == {tool: [] for tool in RULES}
    for tool in RULES:
        reader.launch(tool, "implementer")


def test_grill_setting_is_page_chat_or_unset(tmp_path: Path) -> None:
    assert ConfigReader.load(tmp_path, tmp_path / "u", RULES).config.grill is None
    assert load(tmp_path, {"grill": "page"}).grill == "page"
    assert load(tmp_path, {"grill": "chat"}).grill == "chat"

    with pytest.raises(PipelineConfigError) as raised:
        load(tmp_path, {"grill": "tab"})

    assert "grill: Input should be 'page' or 'chat'" in raised.value.errors[0]


def test_harness_sections_take_a_workflow_with_a_group_and_a_replace_list(tmp_path: Path) -> None:
    config = load(
        tmp_path,
        {
            "harness": {
                "codex": {
                    "workflow": ["implementer", ["test-reviewer", "code-reviewer"]],
                    "replace": ["code-reviewer"],
                    "architect": {"model": "gpt-5", "effort": "high"},
                }
            }
        },
    )

    section = config.harness["codex"]
    assert section.workflow == ["implementer", ["test-reviewer", "code-reviewer"]]
    assert section.replace == ["code-reviewer"]
    assert section.model_dump()["architect"] == {"model": "gpt-5", "effort": "high"}
