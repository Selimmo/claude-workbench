"""The plan format: the contract between the architect agent and the viewer."""

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Annotated, Any, Literal, Self, cast

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    model_validator,
)

from plan_review.file_errors import named_errors
from plan_review.run_id import check_run_id
from plan_review.threads import write_atomically

Status = Literal["added", "modified", "removed", "unchanged"]


class _Strict(BaseModel):
    """Rejects unknown fields, so a typo in an agent-written plan is an error, not a no-op."""

    model_config = ConfigDict(extra="forbid")


class Issue(_Strict):
    id: Annotated[str, AfterValidator(check_run_id)]
    kind: Literal["issue", "prompt"]
    title: str
    url: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _reads_old_number(cls, data: Any) -> Any:
        """Plans written before text ids had `number: 42`; read it as id `"42"`, kind issue."""
        if not isinstance(data, dict):
            return data
        old = cast("dict[str, Any]", data)
        if "number" not in old:
            return old
        number = old["number"]
        if not isinstance(number, int) or isinstance(number, bool):
            raise ValueError("'number' must be a whole number (or use 'id' and 'kind')")
        if "id" in old or "kind" in old:
            raise ValueError("'number' is the old form of 'id' and 'kind'; use only one")
        rest = {k: v for k, v in old.items() if k != "number"}
        return {"id": str(number), "kind": "issue", **rest}


class Member(_Strict):
    id: str
    signature: str
    status: Status


class PlanClass(_Strict):
    id: str
    name: str
    kind: Literal[
        "class", "dataclass", "protocol", "enum", "interface", "function", "module", "type"
    ]
    status: Status
    members: list[Member] = []


class _Edge(_Strict):
    """A directed link. JSON says `from`/`to`; `from` is a Python keyword, hence the aliases."""

    id: str
    source: str = Field(alias="from")
    target: str = Field(alias="to")
    status: Status


class Relation(_Edge):
    kind: Literal["inherits", "implements", "uses", "creates", "contains", "depends_on"]


class Node(_Strict):
    id: str
    name: str
    status: Status


class Step(_Edge):
    label: str


class SequenceFlow(_Strict):
    id: str
    title: str
    kind: Literal["sequence"]
    participants: list[Node]
    steps: list[Step]

    def element_ids(self) -> list[str]:
        return [self.id, *(p.id for p in self.participants), *(s.id for s in self.steps)]

    @model_validator(mode="after")
    def _steps_join_participants(self) -> Self:
        _check_ends(self.steps, {p.id for p in self.participants}, "participant")
        return self


class Link(_Edge):
    label: str | None = None


class Flowchart(_Strict):
    id: str
    title: str
    kind: Literal["flowchart"]
    nodes: list[Node]
    edges: list[Link]

    def element_ids(self) -> list[str]:
        return [self.id, *(n.id for n in self.nodes), *(e.id for e in self.edges)]

    @model_validator(mode="after")
    def _edges_join_nodes(self) -> Self:
        _check_ends(self.edges, {n.id for n in self.nodes}, "node")
        return self


Flow = Annotated[SequenceFlow | Flowchart, Field(discriminator="kind")]


class Component(Node):
    kind: Literal["client", "service", "worker", "database", "queue", "external", "library"]


class Architecture(_Strict):
    nodes: list[Component]
    edges: list[Link]

    @model_validator(mode="after")
    def _edges_join_nodes(self) -> Self:
        _check_ends(self.edges, {n.id for n in self.nodes}, "component")
        return self


class FileChange(_Strict):
    id: str
    path: str
    kind: Literal["code", "test", "config", "doc"]
    change: Literal["added", "modified", "removed"]
    reason: str


class PlannedTest(_Strict):
    """One step of the TDD order; `target` is the id of the element it drives out."""

    id: str
    name: str
    target: str
    behaviour: str


class Risk(_Strict):
    id: str
    kind: Literal["risk", "question"]
    text: str
    severity: Literal["low", "medium", "high"]
    mitigation: str | None = None


class Plan(_Strict):
    issue: Issue
    summary: str
    classes: list[PlanClass] = []
    relations: list[Relation] = []
    flows: list[Flow] = []
    architecture: Architecture | None = None
    files: list[FileChange] = []
    tests: list[PlannedTest] = []
    risks: list[Risk] = []
    acceptance_criteria: list[str] = []
    branch: str | None = None

    def element_ids(self) -> list[str]:
        """Every commentable element's id, in document order."""
        ids = [f"criterion:{n}" for n in range(1, len(self.acceptance_criteria) + 1)]
        for c in self.classes:
            ids += [c.id, *(m.id for m in c.members)]
        ids += [r.id for r in self.relations]
        for flow in self.flows:
            ids += flow.element_ids()
        if self.architecture:
            ids += [n.id for n in self.architecture.nodes]
            ids += [e.id for e in self.architecture.edges]
        ids += [x.id for x in (*self.files, *self.tests, *self.risks)]
        return ids

    @model_validator(mode="after")
    def _prompt_lists_its_criteria(self) -> Self:
        if self.issue.kind == "prompt" and not self.acceptance_criteria:
            raise ValueError("acceptance_criteria: a prompt plan must list its acceptance criteria")
        return self

    @model_validator(mode="after")
    def _ids_are_unique(self) -> Self:
        seen: set[str] = set()
        for id_ in self.element_ids():
            if id_ in seen:
                raise ValueError(f"duplicate id '{id_}': comment threads attach by id")
            seen.add(id_)
        return self

    @model_validator(mode="after")
    def _references_exist(self) -> Self:
        _check_ends(self.relations, {c.id for c in self.classes}, "class")
        known = set(self.element_ids())
        for test in self.tests:
            if test.target not in known:
                raise ValueError(
                    f"{test.id}: 'target' points at unknown element id '{test.target}'"
                )
        return self


def _check_ends(edges: Sequence[_Edge], known: set[str], what: str) -> None:
    for edge in edges:
        for end, ref in (("from", edge.source), ("to", edge.target)):
            if ref not in known:
                raise ValueError(f"{edge.id}: '{end}' points at unknown {what} id '{ref}'")


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
