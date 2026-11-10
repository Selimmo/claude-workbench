"""MarketplacePlugin: a tool that installs plan-review as a plugin through its own program."""

import subprocess
from pathlib import Path

import pytest

from plan_review.harness.distribution import (
    MarketplacePlugin,
    SelfInstall,
    ToolInstall,
    marketplace,
)


def plugin() -> MarketplacePlugin:
    return MarketplacePlugin(
        tool_name="Xtool",
        program="xcli",
        marketplace="m",
        plugin="p",
        marker=".x-plugin/plugin.json",
        after_upgrade="Reload it.",
    )


def test_marketplace_plugin_knows_its_copy_by_its_marker(tmp_path: Path) -> None:
    (tmp_path / ".x-plugin").mkdir()
    assert not plugin().installed_at(tmp_path)

    (tmp_path / ".x-plugin" / "plugin.json").write_text("{}")

    assert plugin().installed_at(tmp_path)


def test_marketplace_plugin_runs_its_steps_with_the_program_on_path(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: list[list[str]] = []

    def run(argv: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(marketplace.shutil, "which", lambda _: "/bin/xcli")
    monkeypatch.setattr(marketplace.subprocess, "run", run)

    assert plugin().available()
    assert plugin().upgrade() == 0
    assert calls == [
        ["/bin/xcli", "plugin", "marketplace", "update", "m"],
        ["/bin/xcli", "plugin", "update", "p@m"],
    ]
    assert "Reload it." in capsys.readouterr().out
    assert plugin().upgrade_commands() == [
        "xcli plugin marketplace update m",
        "xcli plugin update p@m",
    ]


def test_marketplace_plugin_without_its_program_says_so(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(marketplace.shutil, "which", lambda _: None)

    assert not plugin().available()
    assert plugin().upgrade() == 1
    assert "`xcli` not found on PATH: install Xtool first" in capsys.readouterr().err


def test_marketplace_plugin_stops_at_a_failed_step(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def run(argv: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 3)

    monkeypatch.setattr(marketplace.shutil, "which", lambda _: "/bin/xcli")
    monkeypatch.setattr(marketplace.subprocess, "run", run)

    assert plugin().upgrade() == 3
    assert len(calls) == 1


def test_marketplace_plugin_only_says_how_to_install() -> None:
    assert plugin().install_hint() == (
        "Xtool installs plan-review as a plugin: `xcli plugin install p@m`"
    )
    assert isinstance(plugin(), ToolInstall)
    assert not isinstance(plugin(), SelfInstall)
    assert not hasattr(plugin(), "install")
