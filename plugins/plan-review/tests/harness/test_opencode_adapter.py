"""The opencode adapter: its generated files, install and upgrade."""

import json
import re
import shutil
import subprocess
from pathlib import Path, PurePosixPath

import pytest
from conftest import PLUGIN

from plan_review.cli import main
from plan_review.harness import generate, upgrade
from plan_review.harness.adapters import opencode
from plan_review.harness.distribution import releases, wheel
from plan_review.harness.workflow import load_workflow

FILES = PLUGIN / "src" / "plan_review" / "harness" / "adapters" / "opencode_files"
ROLES = ["grill-explorer", "architect", "implementer", "test-reviewer", "code-reviewer"]


def generated() -> dict[PurePosixPath, str]:
    return opencode.HARNESS.files(load_workflow(PLUGIN / "workflow"))


def command() -> str:
    return (FILES / "commands" / "plan-review-ship.md").read_text(encoding="utf-8")


def agent(role: str) -> str:
    return (FILES / "agents" / f"plan-review-{role}.md").read_text(encoding="utf-8")


def frontmatter(text: str) -> str:
    assert text.startswith("---\n")
    return text.split("---\n", 2)[1]


def test_opencode_files_go_inside_the_package() -> None:
    root = PurePosixPath("src/plan_review/harness/adapters/opencode_files")

    assert sorted(generated()) == sorted(
        [
            root / "commands/plan-review-ship.md",
            *(root / f"agents/plan-review-{role}.md" for role in ROLES),
        ]
    )
    for path in generated():
        assert (PLUGIN / path).is_file()


def test_opencode_command_runs_in_the_current_session() -> None:
    text = command()
    ship = load_workflow(PLUGIN / "workflow").ship

    assert text.startswith("---\n")
    header = frontmatter(text)
    assert f"description: {json.dumps(ship.description)}\n" in header
    assert "agent: build\n" in header
    assert "subagent: false\n" in header
    assert "model" not in header
    assert text.split("---\n", 2)[2].startswith(f"\n<!-- {opencode.MARK}")


def test_opencode_command_follows_only_its_own_text() -> None:
    body = command().split("---\n", 2)[2]
    start = body.index(opencode.SHIP_PREAMBLE)

    assert re.search(r"not .{0,40}skill named `ship`", opencode.SHIP_PREAMBLE)
    assert start < body.index("# /ship")
    assert "the input `$ARGUMENTS`" in body


def test_opencode_command_holds_nothing_opencode_would_expand() -> None:
    assert re.findall(r"\$[1-9]|!`", command()) == []


@pytest.mark.parametrize("role", ROLES)
def test_opencode_agents_are_subagents_with_no_model(role: str) -> None:
    workflow = load_workflow(PLUGIN / "workflow").agents[role]
    text = agent(role)
    header = frontmatter(text)

    assert f"description: {json.dumps(workflow.description)}\n" in header
    assert "mode: subagent\n" in header
    assert not re.search(r"model|effort", header)
    assert "AGENTS.md" in text.split("---\n", 2)[2]
    assert "{{" not in text


def permissions(role: str) -> list[tuple[str, str, str]]:
    header = frontmatter(agent(role)).split("permissions:\n", 1)[1]
    return re.findall(r'- action: (\w+)\n\s+resource: "([^"]*)"\n\s+effect: (\w+)\n', header)


@pytest.mark.parametrize("role", ROLES)
def test_opencode_agent_permissions(role: str) -> None:
    found = permissions(role)

    assert ("subagent", "*", "deny") in found
    assert (("edit", "*", "deny") in found) == role.endswith("reviewer")
    assert len(found) == (2 if role.endswith("reviewer") else 1)


def test_opencode_files_name_nothing_from_claude_code_or_codex() -> None:
    forbidden = re.compile(
        r"claude|codex|Monitor|run_in_background|Skill tool|plan-review:[a-z]|\$ship|\.toml",
        re.IGNORECASE,
    )

    for path, text in generated().items():
        assert forbidden.findall(text) == [], path
    for role in ROLES:
        assert "AGENTS.md" in agent(role)
    assert ".opencode/agents/<name>.md" in command()
    assert "plan-review-architect" in command()


def test_opencode_files_use_opencode_wording() -> None:
    assert "edit anything under `.opencode/`" in agent("implementer")
    assert "`subagent` tool" in command()


def test_opencode_waits_under_the_shell_time_limit() -> None:
    text = command()

    assert "plan-review wait ID --timeout 100" in text
    assert "serve ID --detach" in text
    assert "--timeout 240" not in text
    assert opencode.HARNESS.waiting.wait_seconds < 120  # type: ignore[attr-defined]


def test_a_changed_opencode_file_is_reported_stale(tmp_path: Path) -> None:
    shutil.copytree(PLUGIN / "workflow", tmp_path / "workflow")
    generate.write_files(tmp_path)
    target = (
        tmp_path / "src/plan_review/harness/adapters/opencode_files/agents/plan-review-architect.md"
    )
    target.write_bytes(target.read_bytes() + b"<!-- edited -->\n")

    assert generate.stale_files(tmp_path) == [
        "src/plan_review/harness/adapters/opencode_files/agents/plan-review-architect.md"
    ]


# --- install --------------------------------------------------------------------------


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    folder = tmp_path / "home"
    folder.mkdir()
    monkeypatch.setenv("HOME", str(folder))
    monkeypatch.setenv("USERPROFILE", str(folder))
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    return folder


def test_install_writes_the_command_and_agents_to_the_opencode_config(home: Path) -> None:
    assert main(["install", "opencode"]) == 0

    config = home / ".config" / "opencode"
    assert (config / "commands" / "plan-review-ship.md").read_text("utf-8") == command()
    assert sorted(p.name for p in (config / "agents").iterdir()) == sorted(
        f"plan-review-{role}.md" for role in ROLES
    )


def test_install_follows_xdg_config_home_and_treats_empty_as_unset(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "elsewhere"))

    assert main(["install", "opencode"]) == 0

    assert (tmp_path / "elsewhere" / "opencode" / "agents" / "plan-review-architect.md").is_file()
    assert not (home / ".config").exists()

    monkeypatch.setenv("XDG_CONFIG_HOME", "")

    assert main(["install", "opencode"]) == 0

    assert (home / ".config" / "opencode" / "commands" / "plan-review-ship.md").is_file()


def test_install_refuses_a_file_it_did_not_write_and_replaces_its_own(
    home: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    mine = home / ".config" / "opencode" / "commands" / "plan-review-ship.md"
    mine.parent.mkdir(parents=True)
    mine.write_text("my own command\n")

    assert main(["install", "opencode"]) == 1

    assert mine.as_posix() in capsys.readouterr().err
    assert mine.read_text() == "my own command\n"
    assert not (home / ".config" / "opencode" / "agents").exists()  # nothing was written

    mine.write_text(f"<!-- {opencode.MARK} -->\nolder\n")

    assert main(["install", "opencode"]) == 0
    assert mine.read_text("utf-8") == command()


def test_install_opencode_leaves_the_codex_folders_alone(home: Path) -> None:
    assert main(["install", "opencode"]) == 0

    assert not (home / ".agents").exists()
    assert not (home / ".codex").exists()

    assert main(["install", "codex"]) == 0
    ship = home / ".agents" / "skills" / "ship" / "SKILL.md"
    before = ship.read_bytes()

    assert main(["install", "opencode"]) == 0

    assert ship.read_bytes() == before
    assert (home / ".config" / "opencode" / "agents" / "plan-review-architect.md").is_file()
    assert (home / ".codex" / "agents" / "plan-review-architect.toml").is_file()


# --- upgrade --------------------------------------------------------------------------

WHEEL = "https://example.com/plan-review--v1.0.0/plan_review-1.0.0-py3-none-any.whl"


class Runs:
    def __init__(self, fail_on: int | None = None) -> None:
        self.calls: list[list[str]] = []
        self.fail_on = fail_on

    def __call__(self, argv: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        self.calls.append(argv)
        code = 7 if self.fail_on == len(self.calls) else 0
        return subprocess.CompletedProcess(argv, code, stdout="")


@pytest.fixture
def online(home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Runs:
    """A uv tool copy of plan-review, a release with a wheel, and a fake uv."""
    tool = tmp_path / "tools" / "plan-review"
    (tool / "lib").mkdir(parents=True)
    (tool / "uv-receipt.toml").write_text("[tool]\n")
    runs = Runs()
    release = {
        "tag_name": "plan-review--v1.0.0",
        "assets": [{"name": "plan_review-1.0.0-py3-none-any.whl", "browser_download_url": WHEEL}],
    }
    monkeypatch.setattr(upgrade, "PACKAGE_ROOT", tool / "lib")
    monkeypatch.setattr(releases, "fetch_releases", lambda: [release])
    monkeypatch.setattr(wheel.shutil, "which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(wheel.subprocess, "run", runs)
    return runs


def test_upgrade_with_only_opencode_installs_opencode_not_codex(online: Runs) -> None:
    main(["install", "opencode"])

    assert main(["upgrade"]) == 0

    assert online.calls == [
        ["/bin/uv", "tool", "install", "--force", WHEEL],
        ["/bin/uv", "tool", "dir", "--bin"],
        ["/bin/plan-review", "install", "opencode"],
    ]


def test_upgrade_with_codex_and_opencode_refreshes_both(online: Runs) -> None:
    main(["install", "opencode"])
    main(["install", "codex"])

    assert main(["upgrade"]) == 0

    assert online.calls[2][1:] == ["install", "codex"]
    assert online.calls[-1][1:] == ["install", "opencode"]
    assert len(online.calls) == 6


def test_a_failed_first_tool_stops_the_upgrade_with_its_exit_code(online: Runs) -> None:
    main(["install", "opencode"])
    main(["install", "codex"])
    online.fail_on = 3  # `install codex`, after uv installed and named its bin folder

    assert main(["upgrade"]) == 7

    assert len(online.calls) == 3
