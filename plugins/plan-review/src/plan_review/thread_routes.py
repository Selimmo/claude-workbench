"""HTTP routes for comment threads. The page always writes as the owner."""

from pathlib import Path
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from plan_review.plan import PlanFileError, load_plan
from plan_review.threads import Thread, ThreadStore


class NewThread(BaseModel):
    anchor: str
    text: str


class NewReply(BaseModel):
    text: str


def thread_routes(store: ThreadStore, plan_file: Path) -> APIRouter:
    router = APIRouter(prefix="/api/threads")

    def view(thread: Thread, orphans: set[str]) -> dict[str, Any]:
        return {**thread.model_dump(mode="json"), "orphaned": thread.id in orphans}

    def orphan_ids() -> set[str]:
        try:
            ids = set(load_plan(plan_file).element_ids())
        except PlanFileError:
            return set()  # no valid plan to compare against: don't orphan anything
        return {t.id for t in store.orphaned(ids)}

    @router.get("")
    def list_threads() -> dict[str, list[dict[str, Any]]]:  # pyright: ignore[reportUnusedFunction]
        orphans = orphan_ids()
        return {"threads": [view(t, orphans) for t in store.all()]}

    @router.post("", status_code=201)
    def create_thread(body: NewThread) -> dict[str, Any]:  # pyright: ignore[reportUnusedFunction]
        return view(store.create(body.anchor, body.text), orphan_ids())

    @router.post("/{thread_id}/replies")
    def reply(thread_id: str, body: NewReply) -> dict[str, Any]:  # pyright: ignore[reportUnusedFunction]
        return view(store.reply(thread_id, body.text, author="owner"), orphan_ids())

    @router.post("/{thread_id}/resolve")
    def resolve(thread_id: str) -> dict[str, Any]:  # pyright: ignore[reportUnusedFunction]
        return view(store.set_resolved(thread_id, True), orphan_ids())

    @router.post("/{thread_id}/reopen")
    def reopen(thread_id: str) -> dict[str, Any]:  # pyright: ignore[reportUnusedFunction]
        return view(store.set_resolved(thread_id, False), orphan_ids())

    return router
