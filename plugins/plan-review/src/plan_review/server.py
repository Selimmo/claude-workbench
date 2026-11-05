"""The local viewer server: the page, the plan, and live updates."""

import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from plan_review.approval import approval_routes
from plan_review.drafts import DraftNotFound, DraftStore
from plan_review.events import ClaudeEvents, Subscribers
from plan_review.file_errors import BrokenFile
from plan_review.grill import GrillError, GrillStore
from plan_review.grill_drafts import GrillDraftStore
from plan_review.grill_routes import grill_routes
from plan_review.last_event import LastEventStore
from plan_review.plan import PlanFileError, load_plan
from plan_review.resend import resend_routes
from plan_review.review import review_routes
from plan_review.run_id import label
from plan_review.status import StatusStore, status_routes
from plan_review.thread_routes import thread_routes
from plan_review.threads import BlankComment, ThreadNotFound, ThreadStore


def _signature(path: Path) -> tuple[int, int] | None:
    """What we compare to notice a change: modification time and size, or None if missing."""
    try:
        stat = path.stat()
    except FileNotFoundError:
        return None
    return stat.st_mtime_ns, stat.st_size


async def _watch(files: dict[Path, str], interval: float, subscribers: Subscribers) -> None:
    """Announce `files[path]` whenever that file changes.

    Polling rather than OS file events: no extra dependency, and these files change rarely.
    """
    last = {path: _signature(path) for path in files}
    while True:
        await asyncio.sleep(interval)
        for path, event in files.items():
            current = _signature(path)
            if current != last[path]:
                last[path] = current
                await subscribers.send({"type": event})


async def _listen(socket: WebSocket, subscribers: Subscribers) -> None:
    """Hold a push-only socket open until the other side disconnects."""
    await socket.accept()
    subscribers.add(socket)
    try:
        while True:  # listeners never send; this just waits for the disconnect
            await socket.receive_text()
    except WebSocketDisconnect:
        subscribers.remove(socket)


def _error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ThreadNotFound)
    async def not_found(_: Request, error: ThreadNotFound) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        return JSONResponse({"errors": [f"no thread '{error.args[0]}'"]}, status_code=404)

    @app.exception_handler(DraftNotFound)
    async def no_draft(_: Request, error: DraftNotFound) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        return JSONResponse({"errors": [f"no draft '{error.args[0]}'"]}, status_code=404)

    @app.exception_handler(GrillError)
    async def grill_refused(_: Request, error: GrillError) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        status = 404 if error.missing else 409 if error.conflict else 422
        return JSONResponse({"errors": error.errors}, status_code=status)

    @app.exception_handler(BrokenFile)
    async def broken_file(_: Request, error: BrokenFile) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        return JSONResponse({"errors": error.errors}, status_code=422)

    @app.exception_handler(BlankComment)
    async def blank(_: Request, error: BlankComment) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        return JSONResponse({"errors": [str(error)]}, status_code=422)


def _page_routes(app: FastAPI, plan_file: Path, static_dir: Path) -> None:
    @app.get("/grill", response_model=None)
    def grill_page() -> FileResponse:  # pyright: ignore[reportUnusedFunction]
        return FileResponse(static_dir / "index.html")

    @app.get("/", response_model=None)
    def root() -> FileResponse | RedirectResponse:  # pyright: ignore[reportUnusedFunction]
        # Before there is a plan, the grill is the page to look at.
        if not plan_file.exists():
            return RedirectResponse("/grill")
        return FileResponse(static_dir / "index.html")


def create_app(plan_file: Path, static_dir: Path, *, poll_interval: float = 0.5) -> FastAPI:
    comments_file = plan_file.parent / "comments.json"  # sits next to the plan it comments on
    drafts_file = plan_file.parent / "drafts.json"  # the owner's unsent review comments
    status_file = plan_file.parent / "status.json"  # what Claude is doing, set by the CLI
    grill_file = plan_file.parent / "grill.json"  # the grilling before the plan
    grill_drafts_file = plan_file.parent / "grill_drafts.json"  # the owner's unsent answers
    subscribers = Subscribers()  # viewer pages, on /api/updates
    # Claude (through Monitor), on /events. Its last event is kept, but last_event.json is
    # not watched: pages are not told about it, so /api/updates is unchanged.
    kept = LastEventStore(plan_file.parent / "last_event.json")
    events = ClaudeEvents(kept)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
        watched = {
            plan_file: "plan_changed",
            comments_file: "threads_changed",
            drafts_file: "drafts_changed",  # e.g. a second tab of the viewer
            status_file: "status_changed",
            grill_file: "grill_changed",
            grill_drafts_file: "grill_drafts_changed",
        }
        watcher = asyncio.create_task(_watch(watched, poll_interval, subscribers))
        yield
        watcher.cancel()
        with suppress(asyncio.CancelledError):
            await watcher

    app = FastAPI(title="plan-review", lifespan=lifespan)

    @app.get("/api/plan")
    def get_plan() -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        try:
            plan = load_plan(plan_file)
        except PlanFileError as error:
            status = 404 if error.missing else 422
            return JSONResponse({"errors": error.errors}, status_code=status)
        return JSONResponse(plan.model_dump(mode="json", by_alias=True))

    @app.websocket("/api/updates")
    async def updates(socket: WebSocket) -> None:  # pyright: ignore[reportUnusedFunction]
        await _listen(socket, subscribers)

    @app.websocket("/events")
    async def claude_events(socket: WebSocket) -> None:  # pyright: ignore[reportUnusedFunction]
        await _listen(socket, events)

    _error_handlers(app)

    store = ThreadStore(comments_file)
    drafts = DraftStore(drafts_file)
    app.include_router(thread_routes(store, plan_file))
    app.include_router(review_routes(store, drafts, events))
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
    app.include_router(approval_routes(store, drafts, plan_file, events))

    _page_routes(app, plan_file, static_dir)

    @app.middleware("http")
    async def revalidate(  # pyright: ignore[reportUnusedFunction]
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Browsers otherwise cache index.html heuristically and keep an old viewer.
        response = await call_next(request)
        response.headers.setdefault("cache-control", "no-cache")
        return response

    # Mounted last so /api routes win; html=True serves index.html at "/".
    app.mount("/", StaticFiles(directory=static_dir, html=True))
    return app
