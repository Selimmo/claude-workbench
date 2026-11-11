"""The local viewer server: the page, the plan, and live updates."""

import asyncio
from collections.abc import AsyncGenerator, Callable, Sequence
from contextlib import AbstractAsyncContextManager, asynccontextmanager, nullcontext, suppress
from pathlib import Path

from fastapi import APIRouter, FastAPI, WebSocket, WebSocketDisconnect

from plan_review.events.agent_events import AgentEvents
from plan_review.events.event_log import EventLog
from plan_review.events.last_event import LastEventStore
from plan_review.events.resend import resend_routes
from plan_review.events.status import StatusStore, status_routes
from plan_review.events.subscribers import Listeners, Subscribers
from plan_review.grill.drafts import GrillDraftStore
from plan_review.grill.grill import GrillStore
from plan_review.grill.routes import grill_routes
from plan_review.paths.run_id import label
from plan_review.paths.run_paths import RunPaths
from plan_review.review.approval import approval_routes
from plan_review.review.approval_file import ApprovalFile
from plan_review.review.drafts import DraftStore
from plan_review.review.routes import thread_routes
from plan_review.review.service import review_routes
from plan_review.review.threads import ThreadStore
from plan_review.viewer.error_handlers import add_error_handlers
from plan_review.viewer.file_watcher import FileWatcher
from plan_review.viewer.page_routes import serve_page


async def _listen(socket: WebSocket, subscribers: Listeners) -> None:
    """Hold a push-only socket open until the other side disconnects."""
    await socket.accept()
    subscribers.add(socket)
    try:
        while True:  # listeners never send; this just waits for the disconnect
            await socket.receive_text()
    except WebSocketDisconnect:
        subscribers.remove(socket)


def create_app(
    plan_file: Path,
    static_dir: Path,
    *,
    poll_interval: float = 0.5,
    routers: Sequence[APIRouter] = (),
    while_serving: Callable[[Subscribers], AbstractAsyncContextManager[None]] | None = None,
) -> FastAPI:
    run = RunPaths(plan_file.parent)  # the other files sit next to the plan they belong to
    comments_file = run.comments
    drafts_file = run.drafts  # the owner's unsent review comments
    status_file = run.status  # what the agent is doing, set by the CLI
    grill_file = run.grill  # the grilling before the plan
    grill_drafts_file = run.grill_drafts  # the owner's unsent answers
    subscribers = Subscribers()  # viewer pages, on /api/updates
    # the agent, on /events. Its last event is kept, but last_event.json is
    # not watched: pages are not told about it, so /api/updates is unchanged.
    kept = LastEventStore(run.last_event)
    events = AgentEvents(kept, EventLog(run.events))

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
        watched = {
            plan_file: "plan_changed",
            comments_file: "threads_changed",
            drafts_file: "drafts_changed",  # e.g. a second tab of the viewer
            status_file: "status_changed",
            run.approved: "approval_changed",  # approving, from this server or by hand
            grill_file: "grill_changed",
            grill_drafts_file: "grill_drafts_changed",
        }
        watcher = asyncio.create_task(FileWatcher(watched, poll_interval, subscribers).watch())
        async with while_serving(subscribers) if while_serving else nullcontext():
            yield
        watcher.cancel()
        with suppress(asyncio.CancelledError):
            await watcher

    app = FastAPI(title="plan-review", lifespan=lifespan)

    @app.websocket("/api/updates")
    async def updates(socket: WebSocket) -> None:  # pyright: ignore[reportUnusedFunction]
        await _listen(socket, subscribers)

    @app.websocket("/events")
    async def agent_events(socket: WebSocket) -> None:  # pyright: ignore[reportUnusedFunction]
        await _listen(socket, events)

    add_error_handlers(app)

    store = ThreadStore(comments_file)
    approval = ApprovalFile(run.approved)
    drafts = DraftStore(drafts_file)
    app.include_router(thread_routes(store, plan_file))
    app.include_router(review_routes(store, drafts, events, approval))
    statuses = StatusStore(status_file)
    app.include_router(status_routes(statuses))
    app.include_router(resend_routes(kept, statuses, events))
    app.include_router(
        grill_routes(
            GrillStore(grill_file),
            GrillDraftStore(grill_drafts_file),
            events,
            label=label(plan_file.parent.name),
        )
    )
    app.include_router(approval_routes(store, drafts, plan_file, events, approval))

    for router in routers:
        app.include_router(router)

    serve_page(app, plan_file, static_dir)
    return app
