"""What Claude is doing with the owner's review, shown live in the viewer.

The orchestrator sets it with `plan-review status`; it sits in the issue's status.json,
next to comments.json, so a reloaded page still shows it. Only the latest text is kept.
"""

from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel, Field

from plan_review.threads import write_atomically


class Status(BaseModel):
    text: str
    done: bool = False  # False: Claude is still working on it
    at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class StatusStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def get(self) -> Status | None:
        if not self._path.is_file():
            return None
        return Status.model_validate_json(self._path.read_bytes())

    def set(self, text: str, *, done: bool = False) -> Status:
        if not text.strip():
            raise ValueError("status text is empty")
        status = Status(text=text, done=done)
        write_atomically(self._path, status.model_dump_json(indent=2).encode())
        return status

    def clear(self) -> None:
        self._path.unlink(missing_ok=True)


def status_routes(store: StatusStore) -> APIRouter:
    router = APIRouter()

    @router.get("/api/status")
    def get_status() -> dict[str, Status | None]:  # pyright: ignore[reportUnusedFunction]
        return {"status": store.get()}

    return router
