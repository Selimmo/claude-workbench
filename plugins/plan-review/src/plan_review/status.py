"""What Claude is doing with the owner's review, shown live in the viewer.

The orchestrator sets it with `plan-review status`; it sits in the issue's status.json,
next to comments.json, so a reloaded page still shows it. Only the latest text is kept.
"""

from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel, Field, TypeAdapter

from plan_review.file_errors import BrokenFile, read_file
from plan_review.threads import write_atomically


class Status(BaseModel):
    text: str
    done: bool = False  # False: Claude is still working on it
    at: datetime = Field(default_factory=lambda: datetime.now(UTC))


_Status = TypeAdapter(Status)


class StatusStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    @property
    def path(self) -> Path:
        return self._path

    def get(self) -> Status | None:
        return read_file(self._path, _Status)

    def set(self, text: str, *, done: bool = False) -> Status:
        if not text.strip():
            raise ValueError("status text is empty")
        status = Status(text=text, done=done)
        self.set_aside()
        write_atomically(self._path, status.model_dump_json(indent=2).encode())
        return status

    def clear(self) -> None:
        self.set_aside()
        self._path.unlink(missing_ok=True)

    def set_aside(self) -> Path | None:
        """Move a broken status.json to status.json.broken (replacing an older copy there).

        The file holds only this line, so Claude's next status may replace it; the old bytes
        are kept. Returns the new path, or None if nothing was broken."""
        try:
            self.get()
        except BrokenFile:
            aside = self._path.with_name(f"{self._path.name}.broken")
            self._path.replace(aside)
            return aside
        return None


def status_routes(store: StatusStore) -> APIRouter:
    router = APIRouter()

    @router.get("/api/status")
    def get_status() -> dict[str, Status | None]:  # pyright: ignore[reportUnusedFunction]
        return {"status": store.get()}

    return router
