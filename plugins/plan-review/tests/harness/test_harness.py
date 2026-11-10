"""Harness: a tool's key, name and the pieces it uses; and its Wording."""

import dataclasses
import re
from pathlib import Path, PurePosixPath

import pytest
from conftest import PLUGIN

from plan_review.harness.agent_files import MarkdownAgents
from plan_review.harness.distribution import MarketplacePlugin, SelfInstall, ToolInstall
from plan_review.harness.harness import Harness
from plan_review.harness.waiting import SocketWaiting
from plan_review.harness.wording import Wording
from plan_review.harness.workflow import AGENT_NAMES, Workflow, WorkflowText


def wording_fields() -> dict[str, str]:
    return {f.name: f"<{f.name}>" for f in dataclasses.fields(Wording)}


def test_wording_needs_every_fill_in() -> None:
    fields = wording_fields()
    assert Wording(**fields).arguments == "<arguments>"

    del fields["rules_also"]
    with pytest.raises(TypeError):
        Wording(**fields)


def test_wording_cannot_be_changed_after_it_is_made() -> None:
    wording = Wording(**wording_fields())

    with pytest.raises(dataclasses.FrozenInstanceError):
        wording.arguments = "x"  # pyright: ignore[reportAttributeAccessIssue]


def make_harness(distribution: SelfInstall | ToolInstall | None = None) -> Harness:
    return Harness(
        key="x",
        name="Xtool",
        wording=Wording(**wording_fields()),
        agent_files=MarkdownAgents(),
        distribution=distribution
        or MarketplacePlugin("Xtool", "xcli", "m", "p", ".x/plugin.json", "done"),
        waiting=SocketWaiting(listener="Watcher"),
    )


def test_slots_join_the_wording_and_the_waiting_text() -> None:
    harness = make_harness()

    slots = harness.slots()

    assert len(slots) == 18
    assert slots["arguments"] == "<arguments>"
    assert slots["stop_viewer"] == "stop the Watcher and the server task"
    assert slots["grill_listen"] == harness.waiting.grill_listen


def test_every_slot_in_the_workflow_is_a_wording_field_or_a_waiting_text() -> None:
    used = {
        name
        for path in (PLUGIN / "workflow").rglob("*.md")
        for name in re.findall(r"\{\{(\w+)\}\}", path.read_text("utf-8"))
    }

    assert used == set(make_harness().slots())


def test_harness_files_fill_the_workflow_with_its_slots() -> None:
    workflow = Workflow(
        ship=WorkflowText("ship", "Ship it", "# Ship\n"),
        agents={n: WorkflowText(n, "d", "Rules: {{rules_file}}.\n") for n in AGENT_NAMES},
    )

    files = make_harness().files(workflow)

    assert "Rules: <rules_file>." in files[PurePosixPath("agents/architect.md")]


class Installs:
    def __init__(self, code: int) -> None:
        self.code = code

    def installed_at(self, package_root: Path) -> bool:
        return False

    def upgrade(self) -> int:
        return 0

    def upgrade_commands(self) -> list[str]:
        return []

    def install(self) -> int:
        return self.code


def test_harness_install_runs_a_distribution_that_installs_itself() -> None:
    assert make_harness(Installs(5)).install() == 5


def test_harness_install_prints_the_hint_and_exits_2_for_a_tool_that_installs_it(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert make_harness().install() == 2
    assert capsys.readouterr().out == (
        "Xtool installs plan-review as a plugin: `xcli plugin install p@m`\n"
    )
