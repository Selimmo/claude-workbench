"""How a plan is read and saved."""

import json
from pathlib import Path

from pydantic import ValidationError

from plan_review.plan.model import Plan
from plan_review.utils.json_files import named_errors
from plan_review.utils.safe_files import write_atomically


class PlanFileError(Exception):
    """A plan file that is missing or invalid, with one readable line per problem."""

    def __init__(self, errors: list[str], *, missing: bool = False) -> None:
        super().__init__("\n".join(errors))
        self.errors = errors
        self.missing = missing


def load_plan(path: Path) -> Plan:
    if not path.is_file():
        raise PlanFileError([f"{path.as_posix()}: file not found"], missing=True)
    try:
        return Plan.model_validate_json(path.read_bytes())
    except ValidationError as error:
        raise PlanFileError(named_errors(path, error)) from error


def record_branch(path: Path, branch: str) -> None:
    """Set `branch` in the plan file, leaving the rest as the architect wrote it."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["branch"] = branch
    write_atomically(path, (json.dumps(raw, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
