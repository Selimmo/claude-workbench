"""`plan-review upgrade`: the released plugin's newest version, in one command."""

from pathlib import Path

import pytest

from plan_review.cli import main


@pytest.fixture
def claude(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A fake `claude` on PATH that logs each call; returns the log file."""
    log = tmp_path / "calls.log"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "claude"
    fake.write_text(f'#!/bin/sh\necho "$*" >> {log}\nexit "${{FAKE_CLAUDE_EXIT:-0}}"\n')
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir))
    return log


def test_refreshes_the_marketplace_then_updates_the_plugin(claude: Path) -> None:
    exit_code = main(["upgrade"])

    assert exit_code == 0
    assert claude.read_text().splitlines() == [
        "plugin marketplace update claude-workbench",
        "plugin update plan-review@claude-workbench",
    ]


def test_stops_at_a_failed_step_with_its_exit_code(
    claude: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_CLAUDE_EXIT", "3")

    exit_code = main(["upgrade"])

    assert exit_code == 3
    assert claude.read_text().splitlines() == ["plugin marketplace update claude-workbench"]


def test_without_claude_on_path_says_so_and_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))

    exit_code = main(["upgrade"])

    assert exit_code == 1
    assert "`claude` not found on PATH" in capsys.readouterr().err


def test_after_updating_says_how_to_load_the_new_version(
    claude: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["upgrade"])

    assert "/reload-plugins" in capsys.readouterr().out
