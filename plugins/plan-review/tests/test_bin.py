"""bin/plan-review: what Claude Code puts on PATH for the agents and /ship."""

import json
import subprocess
from pathlib import Path

WRAPPER = Path(__file__).parents[1] / "bin" / "plan-review"


def test_runs_the_plugins_own_cli_from_any_directory(tmp_path: Path) -> None:
    result = subprocess.run(
        [str(WRAPPER), "--version"], cwd=tmp_path, capture_output=True, text=True, check=False
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "plan-review 0.1.0\n"


def test_keeps_the_callers_directory_as_the_project_root(tmp_path: Path) -> None:
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "pipeline.json").write_text(json.dumps({"max_review_rounds": 5}))

    result = subprocess.run(
        [str(WRAPPER), "config"], cwd=tmp_path, capture_output=True, text=True, check=False
    )

    assert json.loads(result.stdout)["max_review_rounds"] == 5
