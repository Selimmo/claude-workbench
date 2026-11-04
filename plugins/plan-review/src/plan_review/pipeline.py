"""A project's pipeline settings, from .claude/pipeline.json. Every field is optional."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from plan_review.plan import readable_errors


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Check(_Strict):
    name: str
    run: str


class Viewer(_Strict):
    open: Literal["browser", "none"] = "browser"


class PipelineConfig(_Strict):
    checks: list[Check] = []
    review_rules: list[str] = []
    branch: str = "{issue}-{slug}"
    viewer: Viewer = Viewer()
    max_review_rounds: int = Field(default=3, ge=1)

    @field_validator("branch")
    @classmethod
    def _names_the_issue(cls, branch: str) -> str:
        if "{issue}" not in branch:
            raise ValueError("must contain {issue}")
        return branch


class PipelineConfigError(Exception):
    def __init__(self, errors: list[str]) -> None:
        super().__init__("\n".join(errors))
        self.errors = errors


def load_pipeline(path: Path) -> PipelineConfig:
    if not path.is_file():
        return PipelineConfig()
    try:
        return PipelineConfig.model_validate_json(path.read_text())
    except ValidationError as error:
        raise PipelineConfigError(
            [f"{path.as_posix()}: {line}" for line in readable_errors(error)]
        ) from error
