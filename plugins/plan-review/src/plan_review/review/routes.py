"""HTTP routes for comment threads. The page always writes as the owner.

The owner adds comments and replies through a review (see service.py), never directly."""

from pathlib import Path
from typing import Any

from fastapi import APIRouter

from plan_review.plan.plan_file import PlanFileError, load_plan
from plan_review.review.threads import Thread, ThreadStore


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

    @router.post("/{thread_id}/resolve")
    def resolve(thread_id: str) -> dict[str, Any]:  # pyright: ignore[reportUnusedFunction]
        return view(store.set_resolved(thread_id, True), orphan_ids())

    @router.post("/{thread_id}/reopen")
    def reopen(thread_id: str) -> dict[str, Any]:  # pyright: ignore[reportUnusedFunction]
        return view(store.set_resolved(thread_id, False), orphan_ids())

    return router
