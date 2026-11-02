"""The plan format: the contract between the architect agent and the viewer."""

from collections.abc import Sequence
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

Status = Literal["added", "modified", "removed", "unchanged"]


class _Strict(BaseModel):
    """Rejects unknown fields, so a typo in an agent-written plan is an error, not a no-op."""

    model_config = ConfigDict(extra="forbid")


class Issue(_Strict):
    number: int
    title: str
    url: str | None = None


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

    def element_ids(self) -> list[str]:
        """Every commentable element's id, in document order."""
        ids: list[str] = []
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
        raise PlanFileError([f"{path}: file not found"], missing=True)
    try:
        return Plan.model_validate_json(path.read_text())
    except ValidationError as error:
        raise PlanFileError(readable_errors(error)) from error


def readable_errors(error: ValidationError) -> list[str]:
    """One `location: message` line per error; whole-model checks have no location."""
    lines: list[str] = []
    for e in error.errors():
        where = ".".join(str(part) for part in e["loc"])
        message = e["msg"].removeprefix("Value error, ")  # pydantic's wrapper adds nothing
        lines.append(f"{where}: {message}" if where else message)
    return lines
