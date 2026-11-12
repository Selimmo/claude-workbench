"""The grill page: rounds of questions, the owner's drafts, and one submit that sends them all.

Like the plan review, answers are drafts that only the owner sees until they submit. Submitting
records every answer in grill.json and tells the agent with a single `grill_submitted` event.
"""

from typing import Any

from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from plan_review.events.agent_events import AgentEvents
from plan_review.grill.drafts import AnswerDraft, GrillDraftStore
from plan_review.grill.owner_rules import answers_to_submit, require_draftable
from plan_review.grill.state import MAX_REPLIES
from plan_review.grill.store import GrillStore, drafts_then_grill


class Reopen(BaseModel):
    text: str


def grill_routes(
    store: GrillStore, drafts: GrillDraftStore, events: AgentEvents, *, label: str
) -> APIRouter:
    router = APIRouter()

    @router.get("/api/grill")
    def get_grill() -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        state = store.get()  # GrillError(missing) becomes a 404
        return JSONResponse(
            {**state.model_dump(mode="json"), "label": label, "max_replies": MAX_REPLIES}
        )

    @router.get("/api/grill/drafts")
    def list_drafts() -> dict[str, dict[str, AnswerDraft]]:  # pyright: ignore[reportUnusedFunction]
        return {"drafts": drafts.all()}

    @router.put("/api/grill/drafts/{question_id}")
    def put_draft(question_id: str, draft: AnswerDraft) -> AnswerDraft:  # pyright: ignore[reportUnusedFunction]
        with drafts_then_grill(drafts):
            require_draftable(store.get(), question_id)
            return drafts.put(question_id, draft)

    @router.delete("/api/grill/drafts/{question_id}", status_code=204)
    def discard_draft(question_id: str) -> Response:  # pyright: ignore[reportUnusedFunction]
        drafts.discard(question_id)
        return Response(status_code=204)

    @router.post("/api/grill/submit")
    async def submit() -> dict[str, Any]:  # pyright: ignore[reportUnusedFunction]
        with drafts_then_grill(drafts):
            state = store.get()
            events.check_log()  # before anything is written, as a review does
            answers = answers_to_submit(state, drafts.all())
            drafts.keep_only({a.question_id for a in answers})
            store.submit(answers)
            sent = [a.model_dump(exclude_none=True) for a in answers]
            event = {"type": "grill_submitted", "answers": sent}
            events.record(event)  # before the drafts go, like a review
            drafts.clear({a.question_id for a in answers})
        await events.push(event)
        return {"answers": sent}

    @router.post("/api/grill/confirm")
    async def confirm() -> dict[str, bool]:  # pyright: ignore[reportUnusedFunction]
        events.check_log()  # a confirm can't be repeated, so the log is checked before it
        store.confirm()
        await events.send({"type": "grill_confirmed"})
        return {"confirmed": True}

    @router.post("/api/grill/reopen")
    async def reopen(body: Reopen) -> dict[str, bool]:  # pyright: ignore[reportUnusedFunction]
        events.check_log()  # like a confirm
        store.reopen(body.text)
        await events.send({"type": "grill_reopened", "text": body.text})
        return {"reopened": True}

    return router
