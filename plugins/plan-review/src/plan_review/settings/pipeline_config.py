"""A project's pipeline settings, from .plan-review/config.json. Every field is optional."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from plan_review.settings.steps import OPTIONAL_AGENTS, REQUIRED_AGENTS


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Check(_Strict):
    name: str
    run: str


class Viewer(_Strict):
    open: Literal["browser", "none"] = "browser"


class ModelChoice(_Strict):
    model: str | None = None
    effort: str | None = None  # in the tool's own words


class CustomAgent(_Strict):
    kind: Literal["reviewer"] = "reviewer"  # a later issue can add writers


class HarnessSection(BaseModel):
    """One tool's workflow, and its agents' model and effort: every other key is an agent."""

    model_config = ConfigDict(extra="allow")
    __pydantic_extra__: dict[str, ModelChoice] = Field(init=False)  # pyright: ignore[reportIncompatibleVariableOverride]

    workflow: list[str | list[str]] | None = None
    replace: list[str] | None = None

    @field_validator("workflow")
    @classmethod
    def _groups_have_a_name(
        cls, workflow: list[str | list[str]] | None
    ) -> list[str | list[str]] | None:
        if any(item == [] for item in workflow or []):
            raise ValueError("a group needs at least one name")
        return workflow


class PipelineConfig(_Strict):
    checks: list[Check] = []
    review_rules: list[str] = []
    branch: str = "{issue}-{slug}"
    viewer: Viewer = Viewer()
    grill: Literal["page", "chat"] | None = None  # where /ship --grill asks its questions
    max_review_rounds: int = Field(default=3, ge=1)
    tdd: bool = True
    mutation: str | None = Field(default=None, min_length=1)
    agents: dict[str, CustomAgent] = {}
    harness: dict[str, HarnessSection] = {}

    @field_validator("agents")
    @classmethod
    def _names_are_free(cls, agents: dict[str, CustomAgent]) -> dict[str, CustomAgent]:
        taken = ("workflow", "replace", *REQUIRED_AGENTS, *OPTIONAL_AGENTS)
        for name in agents:
            if name in taken:
                raise ValueError(f"agents.{name}: can't be called {name}: that name is taken")
        return agents

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
