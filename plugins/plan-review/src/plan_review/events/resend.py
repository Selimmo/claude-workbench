"""Seeing and resending the last event sent to the agent.

The agent's watcher may connect after the owner submitted or approved; the viewer then offers
to send the kept event again, unless the agent has already answered it.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from plan_review.events.events import AgentEvents
from plan_review.events.last_event import LastEventStore, answered
from plan_review.events.status import StatusStore


def resend_routes(kept: LastEventStore, status: StatusStore, events: AgentEvents) -> APIRouter:
    router = APIRouter()

    @router.get("/api/last-event")
    def get_last_event() -> dict[str, dict[str, object] | None]:  # pyright: ignore[reportUnusedFunction]
        last = kept.get()
        if last is None:
            return {"last_event": None}
        return {
            "last_event": {
                "type": last.event["type"],
                "sent_at": last.sent_at,
                "answered": answered(status.get(), last),
            }
        }

    @router.post("/api/resend", response_model=None)
    async def resend() -> dict[str, object] | JSONResponse:  # pyright: ignore[reportUnusedFunction]
        last = kept.get()
        if last is None:
            return JSONResponse({"errors": ["nothing has been sent to the agent yet"]}, 409)
        current = status.get()
        if answered(current, last):
            return {"sent": False, "status": current}
        await events.resend(last.event)
        return {"sent": True}

    return router
