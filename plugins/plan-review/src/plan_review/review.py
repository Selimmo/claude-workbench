"""The owner's review: drafts first, then one submit that sends them all.

Like a pull-request review, comments and replies are written as drafts that only the
owner sees. Submitting turns every draft into a thread or a reply at once and tells
Claude with a single `review_submitted` event, so Claude wakes once for the whole batch.
"""

from typing import Any

from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from plan_review.drafts import Draft, DraftStore
from plan_review.events import Subscribers
from plan_review.threads import ThreadStore


class NewDraft(BaseModel):
    text: str
    anchor: str | None = None
    thread_id: str | None = None  # set for a reply in an existing thread


class DraftText(BaseModel):
    text: str


def submit(pending: list[Draft], threads: ThreadStore) -> list[dict[str, str]]:
    """Write each draft as a new thread or a reply, and describe what was written."""
    # Check every reply's thread before writing anything: all or nothing.
    for draft in pending:
        if draft.thread_id is not None:
            threads.get(draft.thread_id)
    comments: list[dict[str, str]] = []
    for draft in pending:
        if draft.thread_id is None:
            thread, kind = threads.create(draft.anchor, draft.text), "comment"
        else:
            thread, kind = threads.reply(draft.thread_id, draft.text, author="owner"), "reply"
        # The same fields each per-comment event used to carry, so an item reads like one.
        comments.append(
            {"type": kind, "thread_id": thread.id, "anchor": thread.anchor, "text": draft.text}
        )
    return comments


def review_routes(threads: ThreadStore, drafts: DraftStore, events: Subscribers) -> APIRouter:
    router = APIRouter()

    @router.get("/api/drafts")
    def list_drafts() -> dict[str, list[Draft]]:  # pyright: ignore[reportUnusedFunction]
        return {"drafts": drafts.all()}

    @router.post("/api/drafts", status_code=201, response_model=None)
    def add_draft(body: NewDraft) -> Draft | JSONResponse:  # pyright: ignore[reportUnusedFunction]
        if body.thread_id is not None:
            # A reply belongs where its thread is; ThreadNotFound becomes a 404.
            anchor = threads.get(body.thread_id).anchor
            return drafts.add(anchor, body.text, thread_id=body.thread_id)
        if body.anchor is None:
            return JSONResponse(
                {"errors": ["a draft needs an anchor or a thread_id"]}, status_code=422
            )
        return drafts.add(body.anchor, body.text)

    @router.put("/api/drafts/{draft_id}")
    def edit_draft(draft_id: str, body: DraftText) -> Draft:  # pyright: ignore[reportUnusedFunction]
        return drafts.edit(draft_id, body.text)

    @router.delete("/api/drafts/{draft_id}", status_code=204)
    def discard_draft(draft_id: str) -> Response:  # pyright: ignore[reportUnusedFunction]
        drafts.discard(draft_id)
        return Response(status_code=204)

    @router.post("/api/review", response_model=None)
    async def submit_review() -> dict[str, Any] | JSONResponse:  # pyright: ignore[reportUnusedFunction]
        # Drafts stay locked for the whole submit, so an edit can't land in between and be
        # lost. Lock order: drafts, then comments (nothing takes them the other way round).
        with drafts.held():
            pending = drafts.all()
            if not pending:
                return JSONResponse({"errors": ["no drafts to submit"]}, status_code=422)
            comments = submit(pending, threads)
            drafts.discard_all({d.id for d in pending})
        await events.send({"type": "review_submitted", "comments": comments})
        return {"comments": comments}

    return router
