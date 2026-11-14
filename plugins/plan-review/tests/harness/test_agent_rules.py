"""What each tool tells the config reader about its agents."""

from pathlib import Path

import pytest
from conftest import PLUGIN

from plan_review.harness.adapters import claude_code, codex, opencode
from plan_review.harness.adapters.codex import toml_sets_model
from plan_review.settings.pipeline_config import ModelChoice


def test_each_tools_defaults_match_today() -> None:
    assert claude_code.RULES.defaults == {
        "grill-explorer": ModelChoice(model="opus", effort="high"),
        "architect": ModelChoice(model="opus", effort="high"),
        "implementer": ModelChoice(model="sonnet"),
        "test-reviewer": ModelChoice(model="opus", effort="high"),
        "code-reviewer": ModelChoice(model="opus", effort="high"),
    }
    assert codex.RULES.defaults == {}
    assert opencode.RULES.defaults == {}


@pytest.mark.parametrize("module", [claude_code, codex, opencode])
def test_each_tools_own_prefix_is_its_wordings_agent_prefix(module: object) -> None:
    harness = module.HARNESS  # pyright: ignore[reportAttributeAccessIssue]

    assert harness.rules.own_prefix == harness.wording.agent_prefix
    assert harness.rules is module.RULES  # pyright: ignore[reportAttributeAccessIssue]


def test_claude_code_takes_only_model_families_and_its_effort_names() -> None:
    assert claude_code.RULES.models == {"opus", "sonnet", "haiku", "fable"}
    assert claude_code.RULES.efforts == {"low", "medium", "high", "xhigh", "max"}
    assert claude_code.RULES.agent_suffix == ".md"
    assert [p.as_posix() for p in claude_code.RULES.project_agent_folders] == [".claude/agents"]
    assert claude_code.RULES.own_agent_file("implementer") == PLUGIN / "agents" / "implementer.md"


def test_claude_code_user_agents_are_in_the_claude_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    assert claude_code.RULES.user_agent_folders() == (tmp_path / ".claude" / "agents",)


def test_codex_follows_the_session_and_reads_toml_agents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.delenv("CODEX_HOME", raising=False)

    assert codex.RULES.models is None
    assert codex.RULES.efforts is None
    assert codex.RULES.agent_suffix == ".toml"
    assert [p.as_posix() for p in codex.RULES.project_agent_folders] == [".codex/agents"]
    assert codex.RULES.user_agent_folders() == (tmp_path / ".codex" / "agents",)
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "elsewhere"))
    assert codex.RULES.user_agent_folders() == (tmp_path / "elsewhere" / "agents",)
    assert codex.RULES.file_sets_model is toml_sets_model
    assert codex.RULES.own_agent_file("implementer").name == "plan-review-implementer.toml"
    assert codex.RULES.own_agent_file("implementer").is_file()


def test_a_codex_toml_that_sets_a_model_or_effort_is_found(tmp_path: Path) -> None:
    def toml(name: str, text: str) -> Path:
        path = tmp_path / name
        path.write_text(text)
        return path

    assert toml_sets_model(toml("a.toml", 'name = "a"\nmodel = "gpt-5"\n'))
    assert toml_sets_model(toml("b.toml", 'name = "b"\nmodel_reasoning_effort = "high"\n'))
    assert not toml_sets_model(toml("c.toml", 'name = "c"\n'))
    assert not toml_sets_model(toml("d.toml", "not = [valid"))
    assert not toml_sets_model(tmp_path / "missing.toml")
    own = codex.RULES.own_agent_file("code-reviewer")
    assert not toml_sets_model(own)


def test_opencode_needs_a_model_for_an_effort(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)

    assert opencode.RULES.effort_needs_model is True
    assert [p.as_posix() for p in opencode.RULES.project_agent_folders] == [
        ".opencode/agent",
        ".opencode/agents",
    ]
    assert opencode.RULES.user_agent_folders() == (
        tmp_path / ".config" / "opencode" / "agent",
        tmp_path / ".config" / "opencode" / "agents",
    )
    assert opencode.RULES.agent_suffix == ".md"
    assert opencode.RULES.own_agent_file("architect").name == "plan-review-architect.md"
