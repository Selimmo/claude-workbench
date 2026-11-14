"""ConfigReader: reading, merging and checking the user's and the project's config.json."""

import json
from dataclasses import replace
from pathlib import Path, PurePosixPath
from typing import Any

import pytest

from plan_review.settings.agent_rules import AgentRules
from plan_review.settings.pipeline_config import ModelChoice, PipelineConfig, PipelineConfigError
from plan_review.settings.reader import ConfigReader

TOOL = "tool"


def make_rules(**changes: Any) -> AgentRules:
    rules = AgentRules(
        own_prefix="own-",
        defaults={},
        models=None,
        efforts=None,
        project_agent_folders=(PurePosixPath(".tool/agents"),),
        user_agent_folders=lambda: (),
        agent_suffix=".md",
        own_agent_file=lambda role: Path("/plugin/agents") / f"{role}.md",
    )
    return replace(rules, **changes)


class Setup:
    """A project folder and a user folder, with the files a test writes into them."""

    def __init__(self, tmp_path: Path) -> None:
        self.root = tmp_path / "project"
        self.user = tmp_path / "user"
        self.root.mkdir()
        self.user.mkdir()

    @property
    def project_file(self) -> Path:
        return self.root / ".plan-review" / "config.json"

    @property
    def user_file(self) -> Path:
        return self.user / "config.json"

    def project(self, config: object) -> Path:
        self.project_file.parent.mkdir(exist_ok=True)
        self.project_file.write_text(json.dumps(config))
        return self.project_file

    def user_config(self, config: object) -> Path:
        self.user_file.write_text(json.dumps(config))
        return self.user_file

    def rules(self, **changes: Any) -> AgentRules:
        """Rules whose folders are `.tool/agents` in the project and `agents` in the user folder."""
        return make_rules(user_agent_folders=lambda: (self.user / "agents",), **changes)

    def reader(self, **changes: Any) -> ConfigReader:
        return ConfigReader.load(self.root, self.user, {TOOL: self.rules(**changes)})

    def project_agent(self, name: str, text: str = "agent") -> Path:
        path = self.root / ".tool" / "agents" / f"{name}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def user_agent(self, name: str, text: str = "agent") -> Path:
        path = self.user / "agents" / f"{name}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path


@pytest.fixture
def setup(tmp_path: Path) -> Setup:
    return Setup(tmp_path)


def test_no_config_anywhere_gives_the_built_in_settings(setup: Setup) -> None:
    config = setup.reader().config

    assert config == PipelineConfig()
    assert config.tdd is True


def test_tdd_is_on_by_default_and_can_be_turned_off(setup: Setup) -> None:
    setup.project({"tdd": False})

    assert setup.reader().config.tdd is False


def test_mutation_is_unset_by_default_and_takes_a_command(setup: Setup) -> None:
    assert setup.reader().config.mutation is None

    setup.user_config({"mutation": "npx stryker run"})
    assert setup.reader().config.mutation == "npx stryker run"

    setup.project({"mutation": "uv run mutmut run"})
    assert setup.reader().config.mutation == "uv run mutmut run"


def test_the_project_file_wins_over_the_user_file_setting_by_setting(setup: Setup) -> None:
    setup.user_config({"branch": "user-{issue}", "harness": {TOOL: {"architect": {"model": "m1"}}}})
    setup.project({"branch": "project-{issue}"})

    config = setup.reader().config

    assert config.branch == "project-{issue}"
    assert config.harness[TOOL].model_dump()["architect"] == {"model": "m1", "effort": None}


def test_one_agents_model_and_effort_merge_field_by_field(setup: Setup) -> None:
    setup.user_config({"harness": {TOOL: {"architect": {"model": "opus"}}}})
    setup.project({"harness": {TOOL: {"architect": {"effort": "high"}}}})

    architect = setup.reader().config.harness[TOOL].model_dump()["architect"]

    assert architect == {"model": "opus", "effort": "high"}


def test_lists_are_replaced_whole(setup: Setup) -> None:
    setup.user_config(
        {
            "checks": [{"name": "a", "run": "a.sh"}],
            "harness": {TOOL: {"workflow": ["implementer", "test-reviewer"]}},
        }
    )
    setup.project(
        {"checks": [{"name": "b", "run": "b.sh"}], "harness": {TOOL: {"workflow": ["implementer"]}}}
    )

    config = setup.reader().config

    assert [check.name for check in config.checks] == ["b"]
    assert config.harness[TOOL].workflow == ["implementer"]


def test_each_setting_says_which_file_it_came_from(setup: Setup) -> None:
    user = setup.user_config({"harness": {TOOL: {"architect": {"model": "opus"}}}})
    project = setup.project({"branch": "x-{issue}"})

    sources = setup.reader().sources()

    assert sources["branch"] == project.as_posix()
    assert sources[f"harness.{TOOL}.architect.model"] == user.as_posix()
    assert sources["grill"] == "built-in"
    assert sources[f"harness.{TOOL}.workflow"] == "built-in"


def test_a_mistake_names_the_file_it_is_in(setup: Setup) -> None:
    user = setup.user_config({"chekcs": []})
    project = setup.project({})
    project.write_text("{bad")

    with pytest.raises(PipelineConfigError) as raised:
        setup.reader()

    lines = raised.value.errors
    assert any(line.startswith(user.as_posix()) and "chekcs" in line for line in lines)
    assert any(line.startswith(project.as_posix()) for line in lines)


def test_an_unknown_harness_is_an_error(setup: Setup) -> None:
    project = setup.project({"harness": {"cursor": {"workflow": ["implementer"]}}})

    with pytest.raises(PipelineConfigError) as raised:
        setup.reader()

    [line] = raised.value.errors
    assert line.startswith(project.as_posix())
    assert 'unknown harness "cursor"' in line
    assert f"known: {TOOL}" in line


@pytest.mark.parametrize(
    "workflow", [[["a", ["b"]]], [[]], [1]], ids=["nested group", "empty group", "number"]
)
def test_a_malformed_workflow_item_is_reported_readably(setup: Setup, workflow: object) -> None:
    setup.project({"harness": {TOOL: {"workflow": workflow}}})

    with pytest.raises(PipelineConfigError) as raised:
        setup.reader()

    assert all(f"harness.{TOOL}.workflow" in line for line in raised.value.errors)
    assert raised.value.errors


@pytest.mark.parametrize("name", ["workflow", "replace", "architect", "implementer"])
def test_a_custom_agent_named_workflow_replace_or_like_a_built_in_is_refused(
    setup: Setup, name: str
) -> None:
    setup.project({"agents": {name: {}}})

    with pytest.raises(PipelineConfigError) as raised:
        setup.reader()

    assert any(
        f"agents.{name}" in line and "can't be called" in line for line in raised.value.errors
    )


def section(workflow: object = None, **more: object) -> dict[str, Any]:
    return {"harness": {TOOL: {**({} if workflow is None else {"workflow": workflow}), **more}}}


def test_no_workflow_gives_the_built_in_one(setup: Setup) -> None:
    reader = setup.reader()

    assert reader.settings(TOOL)["harness"][TOOL]["workflow"] == [
        "implementer",
        "test-reviewer",
        "code-reviewer",
    ]
    assert reader.launch(TOOL, "implementer").agent == "own-implementer"


def test_an_unknown_agent_in_the_workflow_fails_with_where_it_was_looked_for(setup: Setup) -> None:
    setup.project(section(["implementer", "security-reviewer"]))
    reader = setup.reader()

    [line] = reader.problems(TOOL)

    assert "security-reviewer" in line
    assert ".tool/agents/security-reviewer.md" in line
    assert (setup.user / "agents" / "security-reviewer.md").as_posix() in line
    with pytest.raises(PipelineConfigError):
        reader.launch(TOOL, "implementer")


def test_a_custom_reviewer_runs_where_it_is_listed(setup: Setup) -> None:
    setup.project_agent("security-reviewer")
    setup.project(section(["implementer", ["test-reviewer", "security-reviewer"], "code-reviewer"]))

    reader = setup.reader()

    start = reader.launch(TOOL, "security-reviewer")
    assert start.agent == "security-reviewer"
    assert start.kind == "reviewer"
    assert start.review == "review-security-reviewer.md"
    assert reader.launch(TOOL, "code-reviewer").review == "code-review.md"
    assert reader.settings(TOOL)["harness"][TOOL]["workflow"] == [
        "implementer",
        ["test-reviewer", "security-reviewer"],
        "code-reviewer",
    ]


def test_a_custom_reviewer_in_the_user_folder_is_found(setup: Setup) -> None:
    setup.user_agent("security-reviewer")
    setup.project(section(["implementer", "security-reviewer"]))

    reader = setup.reader()

    assert reader.problems(TOOL) == []
    assert reader.launch(TOOL, "security-reviewer").agent == "security-reviewer"


def test_an_agent_setting_for_no_known_agent_is_an_error(setup: Setup) -> None:
    setup.project(section(**{"secrity-reviewer": {"model": "x"}}))

    [line] = setup.reader().problems(TOOL)

    assert f"harness.{TOOL}.secrity-reviewer" in line
    assert "unknown agent" in line
    assert "(from " in line


def test_a_removed_reviewer_is_skipped(setup: Setup) -> None:
    setup.project(section(["implementer", "code-reviewer"]))
    reader = setup.reader()

    assert reader.settings(TOOL)["harness"][TOOL]["workflow"] == ["implementer", "code-reviewer"]
    with pytest.raises(PipelineConfigError, match="not in the workflow"):
        reader.launch(TOOL, "test-reviewer")


def test_a_removed_implementer_makes_the_main_session_write_the_code(setup: Setup) -> None:
    setup.project(section(["code-reviewer"]))
    reader = setup.reader()

    start = reader.launch(TOOL, "implementer")

    assert start.main_session is True
    assert start.agent is None
    assert start.instructions == "/plugin/agents/implementer.md"


def test_a_configured_model_and_effort_are_used_and_the_rest_stay_default(setup: Setup) -> None:
    defaults = {
        "architect": ModelChoice(model="opus", effort="high"),
        "implementer": ModelChoice(model="sonnet"),
        "code-reviewer": ModelChoice(model="opus", effort="high"),
    }
    setup.project_agent("security-reviewer")
    setup.project(
        section(
            ["implementer", ["code-reviewer", "security-reviewer"]],
            architect={"effort": "max"},
            **{"code-reviewer": {"model": "sonnet"}, "security-reviewer": {"model": "haiku"}},
        )
    )
    reader = setup.reader(defaults=defaults)

    def chosen(name: str) -> tuple[str | None, str | None]:
        start = reader.launch(TOOL, name)
        return start.model, start.effort

    assert chosen("architect") == ("opus", "max")
    assert chosen("code-reviewer") == ("sonnet", "high")
    assert chosen("implementer") == ("sonnet", None)
    assert chosen("security-reviewer") == ("haiku", None)


def test_nothing_set_on_a_tool_without_defaults_follows_the_session(setup: Setup) -> None:
    start = setup.reader().launch(TOOL, "architect")

    assert (start.model, start.effort) == (None, None)


def test_plan_review_agents_are_started_by_their_prefixed_name(setup: Setup) -> None:
    reader = setup.reader()

    assert reader.launch(TOOL, "architect").agent == "own-architect"
    assert reader.launch(TOOL, "grill-explorer").agent == "own-grill-explorer"
    assert reader.launch(TOOL, "implementer").agent == "own-implementer"
    assert reader.launch(TOOL, "architect").kind == "architect"


def test_a_projects_own_optional_agent_runs_only_when_replace_lists_it(setup: Setup) -> None:
    setup.project_agent("implementer")

    assert setup.reader().launch(TOOL, "implementer").agent == "own-implementer"

    setup.project(section(replace=["implementer"]))
    assert setup.reader().launch(TOOL, "implementer").agent == "implementer"


def test_your_own_optional_agent_runs_when_replace_lists_it_and_the_project_has_none(
    setup: Setup,
) -> None:
    setup.user_agent("code-reviewer")
    assert setup.reader().launch(TOOL, "code-reviewer").agent == "own-code-reviewer"

    setup.user_config(section(replace=["code-reviewer"]))
    assert setup.reader().launch(TOOL, "code-reviewer").agent == "code-reviewer"

    setup.project(section(replace=[]))
    assert setup.reader().launch(TOOL, "code-reviewer").agent == "own-code-reviewer"


def test_each_replaced_agent_is_named_with_its_file(setup: Setup) -> None:
    assert setup.reader().warnings(TOOL) == []
    implementer = setup.project_agent("implementer")
    reviewer = setup.user_agent("code-reviewer")
    setup.project(section(replace=["implementer", "code-reviewer"]))

    lines = setup.reader().warnings(TOOL)

    assert any("implementer" in line and implementer.as_posix() in line for line in lines)
    assert any("code-reviewer" in line and reviewer.as_posix() in line for line in lines)
    assert len(lines) == 2

    project_reviewer = setup.project_agent("code-reviewer")
    lines = setup.reader().warnings(TOOL)
    assert any(project_reviewer.as_posix() in line for line in lines)
    assert not any(reviewer.as_posix() in line for line in lines)


@pytest.mark.parametrize("replace", [["architect"], ["grill-explorer"], ["security-reviewer"]])
def test_a_bad_replace_fails_before_any_agent_starts(setup: Setup, replace: list[str]) -> None:
    setup.project(section(replace=replace))
    reader = setup.reader()

    [line] = reader.problems(TOOL)

    assert replace[0] in line
    assert f"harness.{TOOL}.replace" in line
    with pytest.raises(PipelineConfigError):
        reader.launch(TOOL, "implementer")


def test_replacing_an_agent_that_is_not_replaceable_says_which_can_be_even_with_a_file(
    setup: Setup,
) -> None:
    setup.project_agent("security-reviewer")
    setup.project(section(["implementer", "security-reviewer"], replace=["security-reviewer"]))

    [line] = setup.reader().problems(TOOL)

    assert "only implementer, test-reviewer, code-reviewer can be" in line


@pytest.mark.parametrize("role", ["architect", "grill-explorer"])
def test_replacing_a_required_agent_says_it_is_always_plan_reviews_own(
    setup: Setup, role: str
) -> None:
    setup.project(section(replace=[role]))

    [line] = setup.reader().problems(TOOL)

    assert f"{role} is always plan-review's own; it can't be replaced" in line


def test_launch_refuses_a_broken_config_too(setup: Setup) -> None:
    setup.project(section(replace=["architect"]))

    with pytest.raises(PipelineConfigError):
        setup.reader().launch(TOOL, "code-reviewer")


def test_a_replaced_role_with_no_file_names_both_folders(setup: Setup) -> None:
    setup.project(section(replace=["code-reviewer"]))
    reader = setup.reader()

    [line] = reader.problems(TOOL)

    assert "code-reviewer" in line
    assert ".tool/agents/code-reviewer.md" in line
    assert (setup.user / "agents" / "code-reviewer.md").as_posix() in line
    with pytest.raises(PipelineConfigError):
        reader.launch(TOOL, "implementer")


def test_a_project_file_not_in_replace_is_not_used_and_says_how_to_turn_it_on(
    setup: Setup,
) -> None:
    project_file = setup.project_agent("code-reviewer")
    reader = setup.reader()

    [line] = reader.warnings(TOOL)

    assert reader.launch(TOOL, "code-reviewer").agent == "own-code-reviewer"
    assert project_file.as_posix() in line
    assert f'"replace": ["code-reviewer"] under harness.{TOOL}' in line


def test_a_user_file_not_in_replace_gives_no_line(setup: Setup) -> None:
    setup.user_agent("code-reviewer")

    assert setup.reader().warnings(TOOL) == []


def test_a_replaced_role_the_workflow_does_not_run_is_only_a_warning(setup: Setup) -> None:
    setup.user_agent("code-reviewer")
    setup.user_config(section(replace=["code-reviewer"]))
    setup.project(section(["implementer", "test-reviewer"]))
    reader = setup.reader()

    assert reader.problems(TOOL) == []
    assert [line for line in reader.warnings(TOOL) if "doesn't run it" in line] == [
        "code-reviewer is in replace but the workflow doesn't run it"
    ]


def test_a_project_file_named_architect_or_grill_explorer_is_ignored_with_a_warning(
    setup: Setup,
) -> None:
    files = [setup.project_agent(name) for name in ("architect", "grill-explorer", "own-architect")]
    reader = setup.reader()

    lines = reader.warnings(TOOL)

    assert reader.launch(TOOL, "architect").agent == "own-architect"
    assert reader.launch(TOOL, "grill-explorer").agent == "own-grill-explorer"
    assert len(lines) == 3
    for file in files:
        assert any(file.as_posix() in line and "is not used" in line for line in lines)


def test_a_model_or_effort_the_tool_does_not_take_fails_before_any_agent_starts(
    setup: Setup,
) -> None:
    setup.project(section(architect={"model": "gpt-5", "effort": "ultra"}))
    reader = setup.reader(models=frozenset({"opus", "sonnet"}), efforts=frozenset({"high"}))

    lines = reader.problems(TOOL)

    assert any("gpt-5" in line and "opus, sonnet" in line for line in lines)
    assert any("ultra" in line and "high" in line for line in lines)


def test_an_effort_without_a_model_fails_where_the_tool_needs_both(setup: Setup) -> None:
    setup.project(section(architect={"effort": "high"}))
    reader = setup.reader(effort_needs_model=True)

    [line] = reader.problems(TOOL)

    assert f"harness.{TOOL}.architect.effort" in line
    assert "model" in line

    setup.user_config(section(architect={"model": "m"}))
    assert setup.reader(effort_needs_model=True).problems(TOOL) == []


def test_where_an_agents_own_file_wins_the_owner_is_warned_once(setup: Setup) -> None:
    def file_sets_model(path: Path) -> bool:
        return "model:" in path.read_text()

    file = setup.project_agent("code-reviewer", "model: x")
    setup.project(section(replace=["code-reviewer"], **{"code-reviewer": {"model": "y"}}))

    lines = setup.reader(file_sets_model=file_sets_model).warnings(TOOL)

    assert [line for line in lines if "wins" in line] == [
        f"code-reviewer: {file.as_posix()} sets its own model, which wins over the config's"
    ]

    setup.project(section(replace=["code-reviewer"]))
    assert not any(
        "wins" in line for line in setup.reader(file_sets_model=file_sets_model).warnings(TOOL)
    )

    setup.project(section(**{"code-reviewer": {"model": "y"}}))
    assert not any(
        "wins" in line for line in setup.reader(file_sets_model=file_sets_model).warnings(TOOL)
    )


def test_a_tool_that_cannot_run_agents_at_once_runs_a_group_in_turn_and_says_so(
    setup: Setup,
) -> None:
    setup.project(section(["implementer", ["test-reviewer", "code-reviewer"]]))

    in_turn = setup.reader(runs_together=False)
    together = setup.reader(runs_together=True)

    assert any("one after another" in line for line in in_turn.warnings(TOOL))
    assert together.warnings(TOOL) == []


def test_a_replaced_role_with_a_model_gives_no_wins_line_where_the_tool_cannot_tell(
    setup: Setup,
) -> None:
    setup.project_agent("code-reviewer", "model: x")
    setup.project(section(replace=["code-reviewer"], **{"code-reviewer": {"model": "y"}}))

    lines = setup.reader(file_sets_model=None).warnings(TOOL)

    assert not any("wins" in line for line in lines)


def test_an_effort_alone_is_enough_for_the_files_own_model_to_win(setup: Setup) -> None:
    file = setup.project_agent("code-reviewer", "model: x")
    setup.project(section(replace=["code-reviewer"], **{"code-reviewer": {"effort": "high"}}))

    lines = setup.reader(file_sets_model=lambda path: True).warnings(TOOL)

    assert [line for line in lines if "wins" in line] == [
        f"code-reviewer: {file.as_posix()} sets its own model, which wins over the config's"
    ]


def test_a_workflow_with_no_group_gives_no_one_after_another_line(setup: Setup) -> None:
    setup.project(section(["implementer", "test-reviewer", "code-reviewer"]))

    assert setup.reader(runs_together=False).warnings(TOOL) == []


def test_launch_says_what_kind_each_agent_is_and_only_reviewers_have_a_review_file(
    setup: Setup,
) -> None:
    reader = setup.reader()

    starts = {
        name: reader.launch(TOOL, name) for name in ("grill-explorer", "architect", "implementer")
    }

    assert {name: (start.kind, start.review) for name, start in starts.items()} == {
        "grill-explorer": ("grill-explorer", None),
        "architect": ("architect", None),
        "implementer": ("implementer", None),
    }
    assert reader.launch(TOOL, "code-reviewer").kind == "reviewer"
    assert reader.launch(TOOL, "code-reviewer").review == "code-review.md"


def test_a_setting_for_an_agent_declared_under_agents_is_known_even_outside_the_workflow(
    setup: Setup,
) -> None:
    setup.project(
        {"agents": {"security-reviewer": {}}, **section(**{"security-reviewer": {"model": "x"}})}
    )

    assert setup.reader().problems(TOOL) == []


def test_the_report_gives_a_custom_reviewer_in_the_workflow_its_model_and_effort(
    setup: Setup,
) -> None:
    setup.project_agent("security-reviewer")
    setup.project(
        section(
            ["implementer", "security-reviewer"],
            **{"security-reviewer": {"model": "haiku", "effort": "low"}},
        )
    )

    resolved = setup.reader().settings(TOOL)["harness"][TOOL]

    assert resolved["security-reviewer"] == {"model": "haiku", "effort": "low"}


def test_an_empty_object_in_a_file_is_reported_as_coming_from_that_file(setup: Setup) -> None:
    project = setup.project({"agents": {}})

    assert setup.reader().sources()["agents"] == project.as_posix()


def test_an_effort_needing_a_model_is_met_by_the_tools_default_model(setup: Setup) -> None:
    setup.project(section(architect={"effort": "high"}))
    reader = setup.reader(effort_needs_model=True, defaults={"architect": ModelChoice(model="m")})

    assert reader.problems(TOOL) == []


def test_a_custom_reviewers_own_model_wins_and_the_owner_is_warned(setup: Setup) -> None:
    file = setup.user_agent("security-reviewer", "model: x")
    setup.project(
        section(["implementer", "security-reviewer"], **{"security-reviewer": {"model": "y"}})
    )

    lines = setup.reader(file_sets_model=lambda path: True).warnings(TOOL)

    assert [line for line in lines if "wins" in line] == [
        f"security-reviewer: {file.as_posix()} sets its own model, which wins over the config's"
    ]


def test_a_problem_from_the_merged_config_names_the_file_it_came_from(setup: Setup) -> None:
    setup.user_config(section(architect={"model": "gpt"}))
    setup.project(section(**{"code-reviewer": {"effort": "bad"}}))
    reader = setup.reader(models={"opus"}, efforts={"high"})

    lines = reader.problems(TOOL)

    assert any(
        f"harness.{TOOL}.architect.model" in line and setup.user_file.as_posix() in line
        for line in lines
    )
    assert any(
        f"harness.{TOOL}.code-reviewer.effort" in line and setup.project_file.as_posix() in line
        for line in lines
    )


# --- gaps found by mutation testing -------------------------------------------------------------


def test_every_kind_of_problem_in_the_project_file_ends_with_that_file(setup: Setup) -> None:
    setup.project_agent("implementer")
    project = setup.project(
        section(
            ["test-reviewer", "implementer", "ghost"],
            replace=["architect"],
            architect={"effort": "high"},
        )
    )
    lines = setup.reader(effort_needs_model=True).problems(TOOL)
    tag = f"(from {project.as_posix()})"

    by_key = {
        "the implementer would come after": [ln for ln in lines if "would come after" in ln],
        "unknown agent ghost: no file": [ln for ln in lines if "ghost: no file" in ln],
        "can't be replaced": [ln for ln in lines if "always plan-review's own" in ln],
        "needs a model": [ln for ln in lines if "needs a model" in ln],
    }
    for kind, found in by_key.items():
        assert len(found) == 1, kind
        assert found[0].endswith(tag), kind


def test_an_unknown_agent_setting_ends_with_its_file(setup: Setup) -> None:
    project = setup.project(section(nobody={"model": "x"}))

    [line] = setup.reader().problems(TOOL)

    assert line == f"harness.{TOOL}.nobody: unknown agent nobody (from {project.as_posix()})"


def test_effort_alone_is_no_problem_where_the_tool_does_not_need_a_model(setup: Setup) -> None:
    setup.project(section(architect={"effort": "high"}))

    assert setup.reader().problems(TOOL) == []


def test_a_model_alone_is_no_problem_where_the_tool_needs_a_model_for_effort(setup: Setup) -> None:
    setup.project(section(architect={"model": "m"}))

    assert setup.reader(effort_needs_model=True).problems(TOOL) == []


def test_a_workflow_agent_without_a_file_gives_no_wins_line_and_no_crash(setup: Setup) -> None:
    setup.project(section(["implementer", "ghost"], ghost={"model": "y"}))
    seen: list[Path] = []

    def file_sets_model(path: Path) -> bool:
        seen.append(path)
        return "model:" in path.read_text()

    lines = setup.reader(file_sets_model=file_sets_model).warnings(TOOL)

    assert not any("wins" in line for line in lines)
    assert seen == []


def test_a_custom_agent_whose_file_sets_no_model_gives_no_wins_line(setup: Setup) -> None:
    setup.project_agent("ghost", "no setting here")
    setup.project(section(["implementer", "ghost"], ghost={"model": "y"}))

    lines = setup.reader(file_sets_model=lambda path: "model:" in path.read_text()).warnings(TOOL)

    assert not any("wins" in line for line in lines)


def test_the_report_gives_replace_as_the_config_set_it(setup: Setup) -> None:
    setup.project_agent("code-reviewer")
    setup.project(section(replace=["code-reviewer"]))

    reader = setup.reader()

    assert reader.settings(TOOL)["harness"][TOOL]["replace"] == ["code-reviewer"]
    assert reader.report(TOOL)["settings"]["harness"][TOOL]["replace"] == ["code-reviewer"]


def test_the_report_for_no_replace_gives_an_empty_list(setup: Setup) -> None:
    assert setup.reader().settings(TOOL)["harness"][TOOL]["replace"] == []


def test_the_report_for_one_tool_lists_only_that_tools_keys_under_from(setup: Setup) -> None:
    rules = {TOOL: setup.rules(), "other": make_rules()}
    reader = ConfigReader.load(setup.root, setup.user, rules)

    for tool in (TOOL, "other"):
        report = reader.report(tool)
        tools = {key.split(".")[1] for key in report["from"] if key.startswith("harness.")}
        assert tools == {tool}
        assert set(report["settings"]["harness"]) == {tool}
    assert {k.split(".")[1] for k in reader.report()["from"] if k.startswith("harness.")} == {
        TOOL,
        "other",
    }


def test_launch_names_the_agent_and_its_kind_in_the_json(setup: Setup) -> None:
    reader = setup.reader()

    normal = reader.launch(TOOL, "code-reviewer").to_json()
    assert (normal["name"], normal["kind"]) == ("code-reviewer", "reviewer")

    setup.project(section(["code-reviewer"]))
    main = setup.reader().launch(TOOL, "implementer").to_json()
    assert (main["name"], main["kind"]) == ("implementer", "implementer")
    assert main["main_session"] is True


def test_the_settings_are_plain_json_values(setup: Setup) -> None:
    setup.project({"checks": [{"name": "a", "run": "a.sh"}]})

    settings = setup.reader().settings()

    assert json.loads(json.dumps(settings)) == settings
    assert settings["checks"] == [{"name": "a", "run": "a.sh"}]


def test_a_non_ascii_config_loads_even_where_the_default_encoding_is_not_utf8(
    setup: Setup, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = Path.read_text

    def windows_like(self: Path, encoding: str | None = None, errors: str | None = None) -> str:
        return real(self, encoding=encoding or "cp1252", errors=errors)

    monkeypatch.setattr(Path, "read_text", windows_like)
    setup.project_file.parent.mkdir(exist_ok=True)
    setup.project_file.write_bytes(
        json.dumps({"review_rules": ["café é"]}, ensure_ascii=False).encode("utf-8")
    )

    assert setup.reader().config.review_rules == ["café é"]


def test_an_unknown_harness_lists_the_known_ones_with_commas(setup: Setup) -> None:
    project = setup.project({"harness": {"nope": {}}})
    rules = {TOOL: setup.rules(), "other": make_rules()}

    with pytest.raises(PipelineConfigError) as raised:
        ConfigReader.load(setup.root, setup.user, rules)

    assert raised.value.errors == [
        f'{project.as_posix()}: harness.nope: unknown harness "nope" (known: {TOOL}, other)'
    ]


def test_the_wording_of_the_step_and_file_problems(setup: Setup) -> None:
    setup.project(section([["implementer", "test-reviewer"], "grill"]))
    [first, second] = setup.reader().problems(TOOL)
    assert first.startswith(
        f"harness.{TOOL}.workflow: the implementer can't be in a group: "
        "nothing runs at the same time as the implementer"
    )
    assert second.startswith(f"harness.{TOOL}.workflow: grill always runs; leave it out")

    setup.project(section(["code-reviewer", "test-reviewer", "implementer"]))
    [late] = setup.reader().problems(TOOL)
    assert late.startswith(
        f"harness.{TOOL}.workflow: the implementer would come after code-reviewer, test-reviewer, "
        "which would review code that isn't written yet: the implementer comes first"
    )

    setup.project(section(replace=["code-reviewer"]))
    [missing] = setup.reader().problems(TOOL)
    assert missing == (
        f"harness.{TOOL}.replace: code-reviewer is listed but there is no file for it, looked in "
        f"{setup.root.as_posix()}/.tool/agents/code-reviewer.md and "
        f"{(setup.user / 'agents').as_posix()}/code-reviewer.md (from "
        f"{setup.project_file.as_posix()})"
    )


def test_a_project_file_named_like_a_required_agent_says_the_own_one_always_runs(
    setup: Setup,
) -> None:
    file = setup.project_agent("architect")

    lines = setup.reader().warnings(TOOL)

    assert lines == [
        f"architect: {file.as_posix()} is not used: plan-review's own architect always runs"
    ]
