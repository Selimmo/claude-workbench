"""The Codex adapter: its generated files, install and upgrade."""

import re
import shutil
import subprocess
import tomllib
from pathlib import Path, PurePosixPath
from typing import Any

import pytest
from conftest import PLUGIN

from plan_review.cli import main
from plan_review.harness import generate, upgrade
from plan_review.harness.adapters import codex
from plan_review.harness.agent_files import toml_multiline
from plan_review.harness.distribution import releases, wheel
from plan_review.harness.workflow import load_workflow

FILES = PLUGIN / "src" / "plan_review" / "harness" / "adapters" / "codex_files"
ROLES = ["architect", "implementer", "test-reviewer", "code-reviewer"]


def generated() -> dict[PurePosixPath, str]:
    return codex.HARNESS.files(load_workflow(PLUGIN / "workflow"))


def skill() -> str:
    return (FILES / "skills" / "ship" / "SKILL.md").read_text(encoding="utf-8")


def test_codex_files_go_inside_the_package() -> None:
    root = PurePosixPath("src/plan_review/harness/adapters/codex_files")

    assert sorted(generated()) == sorted(
        [
            root / "skills/ship/SKILL.md",
            root / "skills/ship/agents/openai.yaml",
            *(root / f"agents/plan-review-{role}.toml" for role in ROLES),
        ]
    )
    for path in generated():
        assert (PLUGIN / path).is_file()


@pytest.mark.parametrize(
    "body", ['C:\\path "quoted" \\n', 'three """ quotes', 'ends with "', 'ends with """', "a\r\nb"]
)
def test_codex_agent_toml_reads_back_exactly(body: str) -> None:
    text = f"key = {toml_multiline(body)}\n"

    assert tomllib.loads(text) == {"key": body}


@pytest.mark.parametrize("role", ROLES)
def test_codex_agents_name_no_model_or_effort(role: str) -> None:
    data = tomllib.loads((FILES / "agents" / f"plan-review-{role}.toml").read_text("utf-8"))

    assert sorted(data) == ["description", "developer_instructions", "name"]


@pytest.mark.parametrize("role", ROLES)
def test_codex_agents_are_prefixed_and_read_agents_md(role: str) -> None:
    data = tomllib.loads((FILES / "agents" / f"plan-review-{role}.toml").read_text("utf-8"))

    assert data["name"] == f"plan-review-{role}"
    assert "AGENTS.md" in data["developer_instructions"]
    assert "CLAUDE.md" not in data["developer_instructions"]
    assert ".claude" not in data["developer_instructions"]


def test_codex_ship_uses_wait_and_detach() -> None:
    for text in ("plan-review wait", "--timeout 240", "serve ID --detach", "plan-review stop"):
        assert text in skill()


def test_codex_ship_waits_for_the_grill_answers_on_the_page() -> None:
    grilling = skill().split("## 1. Settle the decisions", 1)[1].split("## 2. Plan", 1)[0]

    assert "plan-review wait" in grilling
    assert "plan-review grill pending" in grilling


def test_codex_ship_restarts_the_viewer_after_a_timeout() -> None:
    waiting = skill().split("## 3. Review in the viewer", 1)[1]

    assert re.search(r'`\{"type":"timeout"\}`.*?`plan-review serve ID --detach`', waiting, re.S)
    assert "new link" in waiting


def test_codex_ship_never_mentions_a_withdrawal() -> None:
    assert "approval_withdrawn" not in skill()
    assert "withdrawn" not in skill()


def test_codex_ship_catches_up_when_resuming() -> None:
    waiting = skill().split("## 3. Review in the viewer", 1)[1]

    assert "plan-review threads ID" in waiting
    assert "W/approved.json" in waiting


def test_codex_ship_takes_waiting_events_before_the_catch_up() -> None:
    waiting = skill().split("## 3. Review in the viewer", 1)[1]

    first = waiting.index("plan-review wait ID --timeout 0")
    assert first < waiting.index("plan-review threads ID")


def test_codex_ship_confirms_an_event_it_has_already_handled() -> None:
    text = skill()
    grilling = text.split("## 1. Settle the decisions", 1)[1].split("## 2. Plan", 1)[0]
    reviewing = text.split("## 3. Review in the viewer", 1)[1]

    assert "ignore it" not in text
    for part in (grilling, reviewing):
        assert re.search(r'already handled.{0,200}`plan-review status ID "', part, re.S)


def test_codex_ship_starts_the_grill_viewer_detached_when_resuming() -> None:
    grilling = skill().split("## 1. Settle the decisions", 1)[1].split("## 2. Plan", 1)[0]

    assert "start `plan-review serve ID` as" not in grilling
    assert "run `plan-review serve ID --detach`, which returns at once (as in point 2)" in grilling


def test_claude_code_ship_still_ignores_a_repeated_event() -> None:
    text = (PLUGIN / "skills" / "ship" / "SKILL.md").read_text("utf-8")

    assert "(a Resend repeats the same event), ignore it." in text
    assert "shows nothing pending, ignore it." in text


def test_codex_ship_names_nothing_from_claude_code() -> None:
    forbidden = re.compile(
        r"Monitor|run_in_background|\$ARGUMENTS|Skill tool|plan-review:[a-z]|\.claude|CLAUDE\.md"
    )

    assert forbidden.findall(skill()) == []


def test_codex_project_override_is_documented_to_the_skill() -> None:
    assert ".codex/agents/<name>.toml" in skill()
    assert "plan-review-architect" in skill()


def test_ship_runs_only_when_asked_for() -> None:
    policy = (FILES / "skills" / "ship" / "agents" / "openai.yaml").read_text("utf-8")

    assert re.search(r"allow_implicit_invocation:\s*false", policy)


def test_generator_writes_both_adapters() -> None:
    expected = generate.expected_files(PLUGIN)

    names = {p.relative_to(PLUGIN).as_posix() for p in expected}
    assert "skills/ship/SKILL.md" in names
    assert "src/plan_review/harness/adapters/codex_files/skills/ship/SKILL.md" in names
    assert len(expected) == 1 + 4 + 1 + 1 + 4


def test_a_changed_codex_file_is_reported_stale(tmp_path: Path) -> None:
    shutil.copytree(PLUGIN / "workflow", tmp_path / "workflow")
    generate.write_files(tmp_path)
    target = (
        tmp_path / "src/plan_review/harness/adapters/codex_files/agents/plan-review-architect.toml"
    )
    target.write_bytes(target.read_bytes() + b"# edited\n")

    assert generate.stale_files(tmp_path) == [
        "src/plan_review/harness/adapters/codex_files/agents/plan-review-architect.toml"
    ]


# --- install --------------------------------------------------------------------------


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    folder = tmp_path / "home"
    folder.mkdir()
    monkeypatch.setenv("HOME", str(folder))
    monkeypatch.setenv("USERPROFILE", str(folder))
    monkeypatch.delenv("CODEX_HOME", raising=False)
    return folder


def test_install_writes_the_skill_and_agents_to_the_home_folder(home: Path) -> None:
    assert main(["install", "codex"]) == 0

    assert (home / ".agents" / "skills" / "ship" / "SKILL.md").read_text("utf-8") == skill()
    assert (home / ".agents" / "skills" / "ship" / "agents" / "openai.yaml").is_file()
    assert sorted(p.name for p in (home / ".codex" / "agents").iterdir()) == sorted(
        f"plan-review-{role}.toml" for role in ROLES
    )


def test_install_follows_codex_home(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "elsewhere"))

    assert main(["install", "codex"]) == 0

    assert (tmp_path / "elsewhere" / "agents" / "plan-review-architect.toml").is_file()
    assert not (home / ".codex").exists()


def test_install_refuses_a_file_it_did_not_write(
    home: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    mine = home / ".agents" / "skills" / "ship" / "SKILL.md"
    mine.parent.mkdir(parents=True)
    mine.write_text("my own ship skill\n")

    exit_code = main(["install", "codex"])

    assert exit_code == 1
    assert mine.as_posix() in capsys.readouterr().err
    assert mine.read_text() == "my own ship skill\n"
    assert not (home / ".codex").exists()  # nothing at all was written


def test_install_treats_an_empty_codex_home_as_unset(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CODEX_HOME", "")

    assert main(["install", "codex"]) == 0

    assert (home / ".codex" / "agents" / "plan-review-architect.toml").is_file()


def test_install_refuses_a_file_that_is_not_text(
    home: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    mine = home / ".agents" / "skills" / "ship" / "SKILL.md"
    mine.parent.mkdir(parents=True)
    mine.write_bytes(b"\xff\xfe not utf-8")

    assert main(["install", "codex"]) == 1

    assert mine.as_posix() in capsys.readouterr().err


def test_install_overwrites_its_own_older_files(home: Path) -> None:
    main(["install", "codex"])
    target = home / ".codex" / "agents" / "plan-review-architect.toml"
    target.write_text(target.read_text("utf-8") + "# older\n")

    assert main(["install", "codex"]) == 0

    assert "# older" not in target.read_text("utf-8")


def test_install_with_no_files_in_the_copy_says_so(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setattr(codex.HARNESS.distribution, "files", empty)

    assert main(["install", "codex"]) == 1

    assert "Codex files are missing" in capsys.readouterr().err
    assert not (home / ".codex").exists()


def test_install_choices_come_from_the_adapters(home: Path) -> None:
    source = "".join(
        path.read_text("utf-8") for path in (PLUGIN / "src" / "plan_review" / "cli").glob("*.py")
    )

    assert "codex" not in source.lower()
    assert main(["install", "codex"]) == 0


def test_claude_code_install_says_which_command_to_use(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(["install", "claude-code"])

    assert exit_code == 2
    assert "claude plugin install plan-review@claude-workbench" in capsys.readouterr().out


# --- upgrade --------------------------------------------------------------------------


def release(tag: str, *assets: str) -> dict[str, Any]:
    return {
        "tag_name": tag,
        "assets": [
            {"name": n, "browser_download_url": f"https://example.com/{tag}/{n}"} for n in assets
        ],
    }


RELEASES = [
    release("other-tool--v9.0.0", "other-9.0.0-py3-none-any.whl"),
    release("plan-review--v0.2.0", "plan-review-0.2.0.zip"),
    release("plan-review--v0.3.0", "plan-review-0.3.0.zip", "plan_review-0.3.0-py3-none-any.whl"),
    release("plan-review--v0.3.1", "plan-review-0.3.1.zip", "plan_review-0.3.1-py3-none-any.whl"),
    release("plan-review--v0.10.0", "plan_review-0.10.0-py3-none-any.whl"),
    release("plan-review--v0.9.0", "plan_review-0.9.0-py3-none-any.whl"),
    release("plan-review--v0.4.0-rc1", "plan_review-0.4.0rc1-py3-none-any.whl"),
    release("plan-review--v0.11.0", "other_package-0.11.0-py3-none-any.whl"),  # not ours
    {"tag_name": "plan-review--v0.12.0", "assets": None},
]


def test_upgrade_picks_the_newest_plan_review_wheel() -> None:
    assert releases.newest_wheel(RELEASES) == (
        "https://example.com/plan-review--v0.10.0/plan_review-0.10.0-py3-none-any.whl"
    )
    assert releases.newest_wheel(RELEASES[:2]) is None


class Runs:
    def __init__(self, fail_on: int | None = None) -> None:
        self.calls: list[list[str]] = []
        self.fail_on = fail_on
        self.bin_dir = ""  # what `uv tool dir --bin` prints

    def __call__(self, argv: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        self.calls.append(argv)
        code = 7 if self.fail_on == len(self.calls) else 0
        out = self.bin_dir if argv[1:4] == ["tool", "dir", "--bin"] else ""
        return subprocess.CompletedProcess(argv, code, stdout=out)


@pytest.fixture
def online(monkeypatch: pytest.MonkeyPatch) -> Runs:
    runs = Runs()
    monkeypatch.setattr(releases, "fetch_releases", lambda: RELEASES)
    monkeypatch.setattr(wheel.shutil, "which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(wheel.subprocess, "run", runs)
    return runs


WHEEL = "https://example.com/plan-review--v0.10.0/plan_review-0.10.0-py3-none-any.whl"


def test_upgrade_installs_then_runs_the_new_binary(online: Runs) -> None:
    assert codex.HARNESS.distribution.upgrade() == 0

    assert online.calls == [
        ["/bin/uv", "tool", "install", "--force", WHEEL],
        ["/bin/uv", "tool", "dir", "--bin"],
        ["/bin/plan-review", "install", "codex"],
    ]


def test_upgrade_runs_the_binary_from_uvs_tool_bin_folder_when_path_lacks_it(
    online: Runs, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(wheel.shutil, "which", lambda name: "/bin/uv" if name == "uv" else None)
    binary = tmp_path / ("plan-review.exe" if wheel.sys.platform == "win32" else "plan-review")
    binary.write_text("")
    online.bin_dir = f"{tmp_path}\n"

    assert codex.HARNESS.distribution.upgrade() == 0

    assert online.calls[-1] == [str(binary), "install", "codex"]


def test_upgrade_prints_what_to_run_when_the_new_binary_is_not_on_path(
    online: Runs, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(wheel.shutil, "which", lambda name: "/bin/uv" if name == "uv" else None)

    assert codex.HARNESS.distribution.upgrade() == 1

    assert len(online.calls) == 2  # uv ran, and said its bin folder; no binary there or on PATH
    assert "plan-review install codex" in capsys.readouterr().err


def test_upgrade_stops_at_a_failed_step(online: Runs) -> None:
    online.fail_on = 1

    assert codex.HARNESS.distribution.upgrade() == 7
    assert len(online.calls) == 1


def test_upgrade_fails_when_writing_the_files_fails(online: Runs) -> None:
    online.fail_on = 3  # calls 1 and 2: uv installing, uv naming its bin folder

    assert codex.HARNESS.distribution.upgrade() == 7


def test_upgrade_with_no_wheel_in_any_release_prints_what_to_run(
    online: Runs, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(releases, "fetch_releases", lambda: RELEASES[:2])

    assert codex.HARNESS.distribution.upgrade() == 1
    assert "no plan-review release with a wheel" in capsys.readouterr().err
    assert online.calls == []


def test_upgrade_with_an_unreadable_release_list_prints_what_to_run(
    online: Runs, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def garbled() -> list[dict[str, Any]]:
        raise ValueError("not JSON")

    monkeypatch.setattr(releases, "fetch_releases", garbled)

    assert codex.HARNESS.distribution.upgrade() == 1
    assert "can't reach GitHub (not JSON)" in capsys.readouterr().err
    assert online.calls == []


def test_upgrade_with_no_network_prints_what_to_run(
    online: Runs, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def offline() -> list[dict[str, Any]]:
        raise OSError("no network")

    monkeypatch.setattr(releases, "fetch_releases", offline)

    assert codex.HARNESS.distribution.upgrade() == 1
    err = capsys.readouterr().err
    assert "uv tool install --force" in err
    assert "plan-review install codex" in err
    assert online.calls == []


def test_upgrade_without_uv_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    tool = tmp_path / "tool"
    (tool / "lib").mkdir(parents=True)
    (tool / "uv-receipt.toml").write_text("[tool]\n")
    monkeypatch.setattr(upgrade, "PACKAGE_ROOT", tool / "lib")
    monkeypatch.setattr(wheel.shutil, "which", lambda name: None)

    assert main(["upgrade"]) == 1

    err = capsys.readouterr().err
    assert "`uv` not found on PATH" in err
    assert "uv tool install --force" in err
    assert "plan-review install codex" in err


def test_a_uv_tool_copy_is_codex(tmp_path: Path) -> None:
    tool = tmp_path / "tools" / "plan-review"
    root = tool / "lib" / "python3.15"
    root.mkdir(parents=True)
    (tool / "uv-receipt.toml").write_text("[tool]\n")

    assert codex.HARNESS.distribution.installed_at(root)
    assert not codex.HARNESS.distribution.installed_at(tmp_path / "elsewhere")


def test_codex_ship_takes_waiting_events_before_the_grill_catch_up() -> None:
    grilling = skill().split("## 1. Settle the decisions", 1)[1].split("## 2. Plan", 1)[0]

    assert grilling.index("plan-review wait ID --timeout 0") < grilling.index(
        "plan-review grill pending ID` and handle"
    )


def test_claude_code_ship_resumes_the_grill_viewer_as_before() -> None:
    text = (PLUGIN / "skills" / "ship" / "SKILL.md").read_text("utf-8")

    assert "you are resuming: start `plan-review serve ID` as in point 2, give" in text
