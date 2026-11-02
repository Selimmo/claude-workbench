import json
import subprocess
from pathlib import Path

import pytest

from plan_review.cli import main


def test_version_flag_prints_version_and_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["--version"])

    assert exit_code == 0
    assert capsys.readouterr().out == "plan-review 0.1.0\n"


def test_console_script_is_installed() -> None:
    result = subprocess.run(
        ["plan-review", "--version"], capture_output=True, text=True, check=False
    )

    assert result.returncode == 0
    assert result.stdout == "plan-review 0.1.0\n"


def test_schema_prints_the_plan_json_schema(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["schema"])

    schema = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert schema["title"] == "Plan"
    assert "from" in schema["$defs"]["Relation"]["properties"]


def write_plan(tmp_path: Path, plan: object) -> str:
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan))
    return str(path)


VALID_PLAN = {"issue": {"number": 7, "title": "Add hints"}, "summary": "Hint button."}


def test_validate_accepts_a_valid_plan(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["validate", write_plan(tmp_path, VALID_PLAN)])

    assert exit_code == 0
    assert capsys.readouterr().out.startswith("OK")


def test_validate_reports_each_error_with_its_location(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    plan = {**VALID_PLAN, "issue": {"number": "seven", "title": "Add hints"}, "sumary": "typo"}

    exit_code = main(["validate", write_plan(tmp_path, plan)])

    err = capsys.readouterr().err
    assert exit_code == 1
    assert "issue.number: Input should be a valid integer" in err
    assert "sumary: Extra inputs are not permitted" in err


def test_validate_missing_file_exits_2_with_a_clear_message(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(["validate", str(tmp_path / "nope.json")])

    assert exit_code == 2
    assert "nope.json: file not found" in capsys.readouterr().err


def test_validate_malformed_json_is_reported_not_raised(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "plan.json"
    path.write_text("{not json")

    exit_code = main(["validate", str(path)])

    assert exit_code == 1
    assert "Invalid JSON" in capsys.readouterr().err
