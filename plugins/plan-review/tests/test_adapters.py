"""Finding the adapter for the CLI plan-review is installed through."""

from pathlib import Path

from plan_review.adapters import ADAPTERS, installed_adapter
from plan_review.adapters.claude_code import ClaudeCode


def test_a_copy_with_the_plugin_marker_is_claude_code(tmp_path: Path) -> None:
    (tmp_path / ".claude-plugin").mkdir()
    (tmp_path / ".claude-plugin" / "plugin.json").write_text("{}")

    adapter = installed_adapter(tmp_path)

    assert isinstance(adapter, ClaudeCode)
    assert adapter in ADAPTERS


def test_a_copy_with_no_marker_has_no_adapter(tmp_path: Path) -> None:
    assert installed_adapter(tmp_path) is None
