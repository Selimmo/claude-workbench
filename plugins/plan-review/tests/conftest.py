"""Fixtures for the release tooling: a throwaway copy of this repo's layout, with a remote."""

import json
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

# The release scripts are POSIX shell and the file modes are POSIX: Windows skips these.
posix_only = pytest.mark.skipif(
    sys.platform == "win32", reason="POSIX only: shell scripts and file modes"
)

PLUGIN = Path(__file__).parents[1]
TAG = "plan-review--v{}"
# The version under test: release.sh changes it, so tests read it instead of hard-coding it.
PACKAGE_VERSION: str = tomllib.loads((PLUGIN / "pyproject.toml").read_text())["project"]["version"]


# What the shipped viewer page is built from, besides web/src/.
VIEWER_BUILD_FILES = [
    "web/index.html",
    "web/package.json",
    "web/package-lock.json",
    "web/tsconfig.json",
    "web/vite.config.ts",
    "web/.nvmrc",
]


class WindowsStylePath(type(Path())):  # type: ignore[misc]
    """A real path that prints with backslashes on every OS, like Windows."""

    def __str__(self) -> str:
        return super().__str__().replace("/", "\\")

    def as_posix(self) -> str:
        return str(self).replace("\\", "/")


def git(cwd: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def version_of(plugin: Path) -> str:
    return json.loads((plugin / ".claude-plugin" / "plugin.json").read_text())["version"]


@pytest.fixture(autouse=True)
def isolated_git(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    """Git with a known identity and none of the owner's own config (signing, hooks)."""
    config = tmp_path_factory.mktemp("git") / "gitconfig"
    config.write_text(
        "[user]\n\tname = Test\n\temail = test@example.com\n"
        "[init]\n\tdefaultBranch = main\n[commit]\n\tgpgsign = false\n[tag]\n\tgpgsign = false\n"
    )
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A clone of a small claude-workbench, released as 0.1.0; returns the plugin folder.

    It holds this plugin's real release.sh and scripts/, a minimal Python project, and
    one shipped file of each kind, pushed to a bare `origin` with the 0.1.0 tag.
    """
    origin = tmp_path / "origin.git"
    git(tmp_path, "init", "--bare", str(origin))
    root = tmp_path / "work"
    plugin = root / "plugins" / "plan-review"
    (plugin / ".claude-plugin").mkdir(parents=True)
    (root / "LICENSE").write_text("MIT\n")
    (root / "README.md").write_text(
        "# claude-workbench\n\nCodex:\n\n```bash\n"
        "uv tool install https://github.com/o/r/releases/download/"
        "plan-review--v0.1.0/plan_review-0.1.0-py3-none-any.whl\n```\n"
    )
    (root / ".claude-plugin").mkdir()
    (root / ".claude-plugin" / "marketplace.json").write_text(
        json.dumps(
            {"name": "claude-workbench", "plugins": [{"name": "plan-review", "source": "./x"}]}
        )
    )
    (plugin / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "plan-review", "version": "0.1.0"}, indent=2) + "\n"
    )
    (plugin / "pyproject.toml").write_text(
        '[project]\nname = "plan-review"\nversion = "0.1.0"\nrequires-python = ">=3.15"\n'
    )
    (plugin / "README.md").write_text("# plan-review\n")
    (plugin / ".python-version").write_text("3.15\n")
    for shipped in [
        "agents/architect.md",
        "skills/ship/SKILL.md",
        "src/plan_review/cli/__init__.py",
        "web/src/App.tsx",  # built into the shipped page
        "web/src/App.test.tsx",
        *VIEWER_BUILD_FILES,
    ]:
        (plugin / shipped).parent.mkdir(parents=True, exist_ok=True)
        (plugin / shipped).write_text("v1\n")
    (plugin / "bin").mkdir()
    shutil.copy2(PLUGIN / "bin" / "plan-review", plugin / "bin" / "plan-review")
    (plugin / "tests").mkdir()
    (plugin / "tests" / "test_x.py").write_text("v1\n")
    shutil.copy2(PLUGIN / "release.sh", plugin / "release.sh")
    shutil.copytree(PLUGIN / "scripts", plugin / "scripts")
    subprocess.run(["uv", "lock", "--offline", "--quiet"], cwd=plugin, check=True)
    git(root, "init", "--quiet")
    git(root, "add", ".")
    git(root, "commit", "--quiet", "-m", "Initial")
    git(root, "tag", "-a", TAG.format("0.1.0"), "-m", "plan-review 0.1.0")
    git(root, "remote", "add", "origin", str(origin))
    git(root, "push", "--quiet", "origin", "main", "--tags")
    git(root, "branch", "--set-upstream-to=origin/main")
    return plugin
