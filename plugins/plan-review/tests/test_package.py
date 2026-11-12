"""scripts/package.sh: the release zip, which is exactly what Claude Code installs."""

import re
import stat
import subprocess
import zipfile
from pathlib import Path

import pytest
from conftest import PLUGIN, posix_only

pytestmark = posix_only


def package(plugin: Path, out: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["scripts/package.sh", str(out)], cwd=plugin, capture_output=True, text=True, check=False
    )


@pytest.fixture
def built(repo: Path) -> Path:
    """The plugin with its viewer page built, as after `npm --prefix web run build`."""
    static = repo / "src" / "plan_review" / "static"
    static.mkdir()
    (static / "index.html").write_text("<h1>plan-review</h1>")
    return repo


def test_zips_the_plugin_with_its_root_at_the_top(built: Path, tmp_path: Path) -> None:
    result = package(built, tmp_path)

    assert result.returncode == 0, result.stderr
    # It prints the zip's path, for scripts that build it elsewhere.
    assert result.stdout.strip() == str(tmp_path / "plan-review-0.1.0.zip")
    names = zipfile.ZipFile(tmp_path / "plan-review-0.1.0.zip").namelist()
    for shipped in [
        ".claude-plugin/plugin.json",
        "bin/plan-review",
        "agents/architect.md",
        "skills/ship/SKILL.md",
        "src/plan_review/cli/__init__.py",
        "src/plan_review/static/index.html",
        "pyproject.toml",
        "uv.lock",
        "README.md",
        ".python-version",  # bin/plan-review's `uv run` picks Python from it
        "LICENSE",
    ]:
        assert shipped in names


def test_leaves_out_everything_that_does_not_ship(built: Path, tmp_path: Path) -> None:
    (built / "src" / "plan_review" / "__pycache__").mkdir()
    (built / "src" / "plan_review" / "__pycache__" / "cli.cpython-312.pyc").write_text("")
    (built / ".venv").mkdir()
    (built / "agents" / ".DS_Store").write_text("")

    package(built, tmp_path)

    names = zipfile.ZipFile(tmp_path / "plan-review-0.1.0.zip").namelist()
    for left_out in ["tests/", "scripts/", "release.sh", ".venv/", "__pycache__", ".DS_Store"]:
        assert not [name for name in names if left_out in name], left_out


def test_keeps_the_cli_wrapper_executable(built: Path, tmp_path: Path) -> None:
    # Claude Code puts bin/ on PATH; a wrapper without its x bit would not run.
    package(built, tmp_path)

    info = zipfile.ZipFile(tmp_path / "plan-review-0.1.0.zip").getinfo("bin/plan-review")
    assert stat.S_IMODE(info.external_attr >> 16) & stat.S_IXUSR


def test_refuses_without_the_built_viewer_page(repo: Path, tmp_path: Path) -> None:
    result = package(repo, tmp_path)

    assert result.returncode == 1
    assert "npm --prefix web run build" in result.stderr
    assert not list(tmp_path.glob("*.zip"))


def test_replaces_a_zip_left_from_an_earlier_run(built: Path, tmp_path: Path) -> None:
    # zip adds to an existing archive, which would keep its stale entries.
    with zipfile.ZipFile(tmp_path / "plan-review-0.1.0.zip", "w") as stale:
        stale.writestr("stale.txt", "old")

    package(built, tmp_path)

    assert "stale.txt" not in zipfile.ZipFile(tmp_path / "plan-review-0.1.0.zip").namelist()


def test_a_relative_out_dir_is_relative_to_the_callers_directory(
    built: Path, tmp_path: Path
) -> None:
    (tmp_path / "dist").mkdir()

    result = subprocess.run(
        [str(built / "scripts" / "package.sh"), "dist"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "dist" / "plan-review-0.1.0.zip").is_file()


def test_stores_no_extra_file_attributes(built: Path, tmp_path: Path) -> None:
    # zip -X: no macOS/Unix extra fields (owner ids, extended timestamps) in the release zip.
    package(built, tmp_path)

    infos = zipfile.ZipFile(tmp_path / "plan-review-0.1.0.zip").infolist()
    assert [info.filename for info in infos if info.extra] == []


def test_the_built_page_stays_out_of_git_on_main() -> None:
    # It ships only in release zips (the release workflow builds it).
    result = subprocess.run(
        ["git", "check-ignore", "--quiet", "src/plan_review/static/index.html"], cwd=PLUGIN
    )

    assert result.returncode == 0, "static/ is not gitignored"


@pytest.mark.timeout(180)
def test_the_wheel_holds_the_page_and_the_codex_and_opencode_files(tmp_path: Path) -> None:
    page = PLUGIN / "src" / "plan_review" / "static" / "index.html"
    if not page.is_file():
        pytest.skip("the viewer page is not built: run `npm --prefix web run build`")

    subprocess.run(["uv", "build", "--wheel", "--out-dir", str(tmp_path)], cwd=PLUGIN, check=True)

    (wheel,) = tmp_path.glob("plan_review-*.whl")
    names = zipfile.ZipFile(wheel).namelist()
    assert "plan_review/static/index.html" in names
    for shipped in [
        "plan_review/harness/adapters/codex_files/skills/ship/SKILL.md",
        "plan_review/harness/adapters/codex_files/skills/ship/agents/openai.yaml",
        "plan_review/harness/adapters/codex_files/agents/plan-review-architect.toml",
        "plan_review/harness/adapters/opencode_files/commands/plan-review-ship.md",
        "plan_review/harness/adapters/opencode_files/agents/plan-review-architect.md",
    ]:
        assert shipped in names


ROOT = PLUGIN.parents[1]


def test_the_release_workflow_uploads_the_zip_and_the_wheel() -> None:
    workflow = (ROOT / ".github" / "workflows" / "plan-review-release.yml").read_text()

    assert workflow.index("./check.sh") < workflow.index("uv build --wheel")
    assert re.search(r"gh release upload .*\.zip.*\.whl|gh release upload .*wheel_file", workflow)
    assert "plan_review-$VERSION-py3-none-any.whl" in workflow
    # the build job hands the wheel to the publish job along with the zip
    assert "${{ runner.temp }}/dist/*.whl" in workflow


def test_the_shipped_readme_holds_no_wheel_link() -> None:
    # It ships in the zip: a link per release would be a commit per release (the version guard).
    readme = (PLUGIN / "README.md").read_text()

    assert not re.search(r"plan_review-[\d.]+-py3-none-any\.whl", readme)
    assert "releases/download" not in readme
