"""Approving a plan: the hand-off from review to implementation."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from plan_review.events import Subscribers
from plan_review.plan import PlanFileError, load_plan
from plan_review.threads import ThreadStore


def approval_routes(store: ThreadStore, plan_file: Path, events: Subscribers) -> APIRouter:
    router = APIRouter()

    @router.post("/api/approve")
    async def approve() -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        try:
            load_plan(plan_file)
        except PlanFileError as error:
            return JSONResponse({"errors": error.errors}, status_code=422)
        unresolved = [t for t in store.all() if not t.resolved]
        if unresolved:
            message = f"{len(unresolved)} unresolved thread(s): resolve them first"
            return JSONResponse({"errors": [message]}, status_code=409)
        record = {
            "approved_at": datetime.now(UTC).isoformat(),
            # Pins exactly which plan was approved, should the file change afterwards.
            "plan_sha256": hashlib.sha256(plan_file.read_bytes()).hexdigest(),
        }
        (plan_file.parent / "approved.json").write_text(json.dumps(record, indent=2))
        await events.send({"type": "approved"})
        return JSONResponse(record)

    return router
