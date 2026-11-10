"""`plan-review upgrade`: the released plugin's newest version, in one command."""

import subprocess
import sys
from pathlib import Path

import pytest
from conftest import PLUGIN

from plan_review.cli import main
from plan_review.harness import upgrade
from plan_review.harness.adapters import claude_code
from plan_review.harness.adapters.claude_code import ClaudeCode


@pytest.fixture
def claude(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A fake `claude` on PATH that logs each call; returns the log file."""
    log = tmp_path / "calls.log"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "claude"
    fake.write_text(f'#!/bin/sh\necho "$*" >> {log}\nexit "${{FAKE_CLAUDE_EXIT:-0}}"\n')
    fake.chmod(0o755)
    if sys.platform == "win32":
        # npm's layout: an extensionless sh shim next to claude.cmd, which is what starts.
        (bin_dir / "claude.cmd").write_text(
            f'@echo off\n>>"{log}" echo %*\n'
            "if not defined FAKE_CLAUDE_EXIT set FAKE_CLAUDE_EXIT=0\n"
            "exit /b %FAKE_CLAUDE_EXIT%\n"
        )
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

    err = capsys.readouterr().err
    assert exit_code == 1
    assert "Claude Code was not found on PATH" in err
    assert "claude plugin marketplace update claude-workbench" in err
    assert "claude plugin update plan-review@claude-workbench" in err


def test_the_adapter_itself_says_so_without_claude_on_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))

    assert ClaudeCode().upgrade() == 1
    assert "`claude` not found on PATH" in capsys.readouterr().err


def test_after_updating_says_how_to_load_the_new_version(
    claude: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["upgrade"])

    assert "/reload-plugins" in capsys.readouterr().out


def test_runs_the_claude_that_path_lookup_finds(monkeypatch: pytest.MonkeyPatch) -> None:
    # On Windows an npm-installed claude is claude.cmd, which only its full path starts.
    calls: list[list[str]] = []

    def run(argv: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(claude_code.shutil, "which", lambda _: "C:/npm/claude.cmd")
    monkeypatch.setattr(claude_code.subprocess, "run", run)

    assert main(["upgrade"]) == 0
    assert calls == [
        ["C:/npm/claude.cmd", "plugin", "marketplace", "update", "claude-workbench"],
        ["C:/npm/claude.cmd", "plugin", "update", "plan-review@claude-workbench"],
    ]


def test_the_commands_it_prints_are_the_steps_upgrade_runs(claude: Path) -> None:
    ClaudeCode().upgrade()

    ran = [f"claude {line}" for line in claude.read_text().splitlines()]
    assert ClaudeCode().upgrade_commands() == ran


def test_upgrade_that_cannot_tell_prints_what_to_run_and_changes_nothing(
    claude: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(upgrade, "PACKAGE_ROOT", tmp_path / "nowhere")

    exit_code = main(["upgrade"])

    err = capsys.readouterr().err
    assert exit_code == 1
    assert "can't tell how it was installed" in err
    assert "claude plugin update plan-review@claude-workbench" in err
    assert not claude.exists()  # the fake claude was never called


def test_upgrade_package_root_is_the_plugin_folder() -> None:
    assert upgrade.PACKAGE_ROOT == PLUGIN
