"""Approving a plan: the hand-off from review to implementation."""

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from plan_review.events.agent_events import AgentEvents
from plan_review.plan.plan_file import PlanFileError, load_plan
from plan_review.review.approval_file import ApprovalFile, ApprovalRecord
from plan_review.review.drafts import DraftStore
from plan_review.review.threads import ResolveRefused, ThreadStore


def approval_routes(
    store: ThreadStore,
    drafts: DraftStore,
    plan_file: Path,
    events: AgentEvents,
    approval_file: ApprovalFile,
) -> APIRouter:
    router = APIRouter()

    @router.get("/api/approve")
    def approval() -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        existing = approval_file.read()
        if existing is None:
            return JSONResponse({"approved": False})
        return JSONResponse({"approved": True, **existing.model_dump()})

    @router.post("/api/approve")
    async def approve() -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        try:
            load_plan(plan_file)
        except PlanFileError as error:
            return JSONResponse({"errors": error.errors}, status_code=422)
        approval_file.read()  # a broken approved.json is reported, never replaced
        # Drafts stay locked from the checks to the write, as in a review submit, so a review
        # sent at the same moment can't land in between. Nothing is awaited inside the lock.
        with drafts.held():
            unsent = len(drafts.all())
            if unsent:
                # Not auto-submitted: submitted comments open threads, which block approval anyway.
                message = f"{unsent} unsent draft(s): submit or discard them first"
                return JSONResponse({"errors": [message]}, status_code=409)
            unresolved = [t for t in store.all() if not t.resolved]
            if unresolved:
                message = f"{len(unresolved)} unresolved thread(s): resolve them first"
                return JSONResponse({"errors": [message]}, status_code=409)
            waiting = [t for t in store.all() if t.awaiting_answer]
            if waiting:
                refused = str(ResolveRefused(waiting[0].id))
                return JSONResponse({"errors": [refused]}, status_code=409)
            events.check_log()  # before the file is written: a saved approval must reach the agent
            record = ApprovalRecord(
                approved_at=datetime.now(UTC).isoformat(),
                # Pins exactly which plan was approved, should the file change afterwards.
                plan_sha256=hashlib.sha256(plan_file.read_bytes()).hexdigest(),
            )
            approval_file.write(record)
            event = {"type": "approved"}
            events.record(event)
        await events.push(event)
        return JSONResponse(record.model_dump())

    return router
