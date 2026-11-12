"""Finding the adapter for the CLI plan-review is installed through."""

from pathlib import Path

import pytest

from plan_review.cli import main
from plan_review.harness.adapters import (
    all_adapters,
    claude_code,
    codex,
    installed_adapters,
    opencode,
)


def test_a_copy_with_the_plugin_marker_is_claude_code(tmp_path: Path) -> None:
    (tmp_path / ".claude-plugin").mkdir()
    (tmp_path / ".claude-plugin" / "plugin.json").write_text("{}")

    adapter = installed_adapters(tmp_path)[0]

    assert adapter is claude_code.HARNESS
    assert adapter in all_adapters()


def test_a_copy_with_no_marker_has_no_adapter(tmp_path: Path) -> None:
    assert installed_adapters(tmp_path) == []


def test_a_plugin_folder_still_goes_to_claude_code_even_under_a_uv_tool(tmp_path: Path) -> None:
    (tmp_path / "uv-receipt.toml").write_text("[tool]\n")
    plugin = tmp_path / "lib" / "plugin"
    (plugin / ".claude-plugin").mkdir(parents=True)
    (plugin / ".claude-plugin" / "plugin.json").write_text("{}")

    assert installed_adapters(plugin)[0] is claude_code.HARNESS


@pytest.fixture
def uv_copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A uv tool copy of plan-review, and an empty home with no Codex or opencode folders."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    tool = tmp_path / "tools" / "plan-review"
    root = tool / "lib" / "python3.15"
    root.mkdir(parents=True)
    (tool / "uv-receipt.toml").write_text("[tool]\n")
    return root


def test_installed_adapters_lists_every_tool_that_recognises_the_copy(uv_copy: Path) -> None:
    assert installed_adapters(uv_copy) == []

    main(["install", "opencode"])

    assert installed_adapters(uv_copy) == [opencode.HARNESS]

    main(["install", "codex"])

    assert installed_adapters(uv_copy) == [codex.HARNESS, opencode.HARNESS]
    assert installed_adapters(uv_copy)[0] is codex.HARNESS
