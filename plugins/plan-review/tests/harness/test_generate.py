"""workflow/ is written once; a generator writes each CLI's files from it."""

import os
import subprocess
import sys
from pathlib import Path, PurePosixPath

import pytest
from conftest import PLUGIN

from plan_review.harness import generate
from plan_review.harness.adapters import claude_code
from plan_review.harness.workflow import fill, load_workflow

AGENTS = ["grill-explorer", "architect", "implementer", "test-reviewer", "code-reviewer"]


def write_sample(root: Path) -> None:
    """A small workflow/ with the /ship text and the five agents."""
    (root / "workflow" / "agents").mkdir(parents=True)
    (root / "workflow" / "ship.md").write_text(
        "---\nname: ship\ndescription: Ship it: plan to commit\n---\n\n# Ship {{arguments}}\n"
    )
    for name in AGENTS:
        (root / "workflow" / "agents" / f"{name}.md").write_text(
            f"---\nname: {name}\ndescription: The {name}\n---\n\nYou are the {name}.\n"
            "Rules: `{{rules_file}}`.\n"
        )


def test_fill_replaces_slots_and_leaves_other_braces_alone() -> None:
    text = "{{one}} and {issue}, $ARGUMENTS, <id>, {{two}}"

    assert fill(text, {"one": "1", "two": "2"}) == "1 and {issue}, $ARGUMENTS, <id>, 2"


def test_fill_refuses_a_slot_with_no_value() -> None:
    with pytest.raises(ValueError, match="nope"):
        fill("a {{nope}} b", {"other": "x"})


def test_load_workflow_reads_ship_and_the_four_agents(tmp_path: Path) -> None:
    write_sample(tmp_path)

    workflow = load_workflow(tmp_path / "workflow")

    assert (workflow.ship.name, workflow.ship.description) == ("ship", "Ship it: plan to commit")
    assert workflow.ship.body == "\n# Ship {{arguments}}\n"
    assert sorted(workflow.agents) == sorted(AGENTS)
    architect = workflow.agents["architect"]
    assert (architect.name, architect.description) == ("architect", "The architect")
    assert architect.body.startswith("\nYou are the architect.")


def test_claude_code_files_go_where_the_plugin_ships_them(tmp_path: Path) -> None:
    write_sample(tmp_path)

    files = claude_code.HARNESS.files(load_workflow(tmp_path / "workflow"))

    assert sorted(files) == sorted(
        [PurePosixPath("skills/ship/SKILL.md"), *(PurePosixPath(f"agents/{a}.md") for a in AGENTS)]
    )
    ship = files[PurePosixPath("skills/ship/SKILL.md")]
    assert ship.startswith("---\nname: ship\ndescription: Ship it: plan to commit\n")
    assert "disable-model-invocation: true\n---\n" in ship
    assert "# Ship $ARGUMENTS" in ship
    architect = files[PurePosixPath("agents/architect.md")]
    assert "model: opus\n" in architect
    assert "Rules: `CLAUDE.md`." in architect


def test_generate_writes_every_file_with_lf_endings(tmp_path: Path) -> None:
    write_sample(tmp_path)

    generate.write_files(tmp_path)

    expected = generate.expected_files(tmp_path)
    assert len(expected) == 6 + 7 + 6  # Claude Code, Codex, then opencode
    for path, content in expected.items():
        assert path.read_bytes() == content
        assert b"\r" not in content


def test_check_passes_on_fresh_output_and_writes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_sample(tmp_path)
    generate.write_files(tmp_path)
    ship = tmp_path / "skills" / "ship" / "SKILL.md"
    os.utime(ship, (1_000_000, 1_000_000))
    before = {p: (p.stat().st_mtime_ns, p.read_bytes()) for p in tmp_path.rglob("*") if p.is_file()}

    assert generate.main(["--check", "--root", str(tmp_path)]) == 0

    assert {p: (p.stat().st_mtime_ns, p.read_bytes()) for p in before} == before


def test_check_fails_naming_a_changed_or_missing_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_sample(tmp_path)
    generate.write_files(tmp_path)
    (tmp_path / "agents" / "architect.md").write_text("edited by hand\n")
    (tmp_path / "skills" / "ship" / "SKILL.md").unlink()

    exit_code = generate.main(["--check", "--root", str(tmp_path)])

    err = capsys.readouterr().err
    assert exit_code == 1
    assert "agents/architect.md" in err
    assert "skills/ship/SKILL.md" in err
    assert "python -m plan_review.harness.generate" in err


def test_main_without_check_writes_the_files(tmp_path: Path) -> None:
    write_sample(tmp_path)

    assert generate.main(["--root", str(tmp_path)]) == 0

    assert generate.stale_files(tmp_path) == []
    assert (tmp_path / "skills" / "ship" / "SKILL.md").is_file()


def test_a_subfolder_in_a_generated_folder_is_left_alone(tmp_path: Path) -> None:
    write_sample(tmp_path)
    generate.write_files(tmp_path)
    (tmp_path / "agents" / "notes").mkdir()

    assert generate.stale_files(tmp_path) == []
    generate.write_files(tmp_path)

    assert (tmp_path / "agents" / "notes").is_dir()


def test_a_leftover_file_in_a_generated_folder_is_stale(tmp_path: Path) -> None:
    write_sample(tmp_path)
    generate.write_files(tmp_path)
    leftover = tmp_path / "agents" / "old.md"
    leftover.write_text("an agent that was removed\n")

    assert generate.stale_files(tmp_path) == ["agents/old.md"]

    generate.write_files(tmp_path)

    assert not leftover.exists()
    assert generate.stale_files(tmp_path) == []


def test_a_dotfile_in_a_generated_folder_is_not_stale(tmp_path: Path) -> None:
    write_sample(tmp_path)
    generate.write_files(tmp_path)
    dotfile = tmp_path / "agents" / ".DS_Store"
    dotfile.write_bytes(b"finder")

    assert generate.stale_files(tmp_path) == []

    generate.write_files(tmp_path)

    assert dotfile.exists()


def test_the_committed_output_matches_the_workflow() -> None:
    assert generate.stale_files(PLUGIN) == []


def test_check_sh_runs_the_stale_check() -> None:
    script = (PLUGIN / "check.sh").read_text()

    assert "python -m plan_review.harness.generate --check" in script


def test_the_generator_runs_as_a_module(tmp_path: Path) -> None:
    write_sample(tmp_path)

    result = subprocess.run(
        [sys.executable, "-m", "plan_review.harness.generate", "--check", "--root", str(tmp_path)],
        cwd=PLUGIN,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1, result.stderr
    assert "stale generated files" in result.stderr


def test_generate_package_root_is_the_plugin_folder() -> None:
    assert generate.PACKAGE_ROOT == PLUGIN
