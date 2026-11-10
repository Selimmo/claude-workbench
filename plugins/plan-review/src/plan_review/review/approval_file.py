"""approved.json: the one place that reads or writes it."""

from pathlib import Path

from pydantic import BaseModel, TypeAdapter

from plan_review.utils.json_files import read_file
from plan_review.utils.safe_files import write_atomically


class ApprovalRecord(BaseModel):
    approved_at: str
    plan_sha256: str


_Record = TypeAdapter(ApprovalRecord)


class ApprovalFile:
    def __init__(self, path: Path) -> None:
        self._path = path

    def read(self) -> ApprovalRecord | None:
        """The record; None if the plan isn't approved; BrokenFile if the file doesn't parse."""
        return read_file(self._path, _Record)

    def write(self, record: ApprovalRecord) -> None:
        self.read()  # a broken approved.json is reported, never replaced
        write_atomically(self._path, _Record.dump_json(record, indent=2))
