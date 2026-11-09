"""Approving a plan: the hand-off from review to implementation."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, TypeAdapter

from plan_review.drafts import DraftStore
from plan_review.events import AgentEvents
from plan_review.file_errors import read_file
from plan_review.plan import PlanFileError, load_plan
from plan_review.threads import ThreadStore


class ApprovalRecord(BaseModel):
    approved_at: str
    plan_sha256: str


_Record = TypeAdapter(ApprovalRecord)


def approval_routes(
    store: ThreadStore, drafts: DraftStore, plan_file: Path, events: AgentEvents
) -> APIRouter:
    router = APIRouter()

    record_file = plan_file.parent / "approved.json"

    @router.get("/api/approve")
    def approval() -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        existing = read_file(record_file, _Record)
        if existing is None:
            return JSONResponse({"approved": False})
        return JSONResponse({"approved": True, **existing.model_dump()})

    @router.post("/api/approve")
    async def approve() -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        try:
            load_plan(plan_file)
        except PlanFileError as error:
            return JSONResponse({"errors": error.errors}, status_code=422)
        read_file(record_file, _Record)  # a broken approved.json is reported, never replaced
        unsent = len(drafts.all())
        if unsent:
            # Not auto-submitted: submitted comments open threads, which block approval anyway.
            message = f"{unsent} unsent draft(s): submit or discard them first"
            return JSONResponse({"errors": [message]}, status_code=409)
        unresolved = [t for t in store.all() if not t.resolved]
        if unresolved:
            message = f"{len(unresolved)} unresolved thread(s): resolve them first"
            return JSONResponse({"errors": [message]}, status_code=409)
        record = {
            "approved_at": datetime.now(UTC).isoformat(),
            # Pins exactly which plan was approved, should the file change afterwards.
            "plan_sha256": hashlib.sha256(plan_file.read_bytes()).hexdigest(),
        }
        record_file.write_text(json.dumps(record, indent=2))
        await events.send({"type": "approved"})
        return JSONResponse(record)

    return router
