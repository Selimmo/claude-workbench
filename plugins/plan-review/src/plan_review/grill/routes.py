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
from plan_review.grill.grill import MAX_REPLIES, GrillError, GrillStore, SubmittedAnswer


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
        # Checked under the drafts lock, like submit, so a submit cannot answer the question
        # between this check and the write.
        with drafts.held():
            question = store.get().question(question_id)
            if question.answer is not None:
                raise GrillError([f"question '{question_id}' is already answered"], missing=True)
            return drafts.put(question_id, draft)

    @router.delete("/api/grill/drafts/{question_id}", status_code=204)
    def discard_draft(question_id: str) -> Response:  # pyright: ignore[reportUnusedFunction]
        drafts.discard(question_id)
        return Response(status_code=204)

    @router.post("/api/grill/submit")
    async def submit() -> dict[str, Any]:  # pyright: ignore[reportUnusedFunction]
        # Drafts stay locked for the whole submit so an edit cannot land in between and be
        # lost. Lock order: drafts, then grill.json (the store takes its own lock).
        with drafts.held():
            # A draft for a question that is no longer open (the agent closed it meanwhile) is
            # dropped rather than refusing the whole submit.
            open_ids = {q.id for q in store.get().open_questions()}
            events.check_log()  # before anything is written, as a review does
            drafts.keep_only(open_ids)
            answers = [
                SubmittedAnswer(question_id=qid, **draft.model_dump())
                for qid, draft in drafts.all().items()
            ]
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
