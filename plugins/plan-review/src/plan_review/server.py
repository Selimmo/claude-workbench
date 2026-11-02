"""The local viewer server: the page, the plan, and live updates."""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from plan_review.approval import approval_routes
from plan_review.events import Subscribers
from plan_review.plan import PlanFileError, load_plan
from plan_review.thread_routes import thread_routes
from plan_review.threads import BlankComment, ThreadNotFound, ThreadStore


def _signature(path: Path) -> tuple[int, int] | None:
    """What we compare to notice a change: modification time and size, or None if missing."""
    try:
        stat = path.stat()
    except FileNotFoundError:
        return None
    return stat.st_mtime_ns, stat.st_size


async def _watch(path: Path, interval: float, subscribers: Subscribers) -> None:
    # Polling rather than OS file events: no extra dependency, and plans change rarely.
    last = _signature(path)
    while True:
        await asyncio.sleep(interval)
        current = _signature(path)
        if current != last:
            last = current
            await subscribers.send({"type": "plan_changed"})


async def _listen(socket: WebSocket, subscribers: Subscribers) -> None:
    """Hold a push-only socket open until the other side disconnects."""
    await socket.accept()
    subscribers.add(socket)
    try:
        while True:  # listeners never send; this just waits for the disconnect
            await socket.receive_text()
    except WebSocketDisconnect:
        subscribers.remove(socket)


def create_app(plan_file: Path, static_dir: Path, *, poll_interval: float = 0.5) -> FastAPI:
    subscribers = Subscribers()  # viewer pages, on /api/updates
    events = Subscribers()  # Claude (through Monitor), on /events

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
        watcher = asyncio.create_task(_watch(plan_file, poll_interval, subscribers))
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

    @app.exception_handler(ThreadNotFound)
    async def not_found(_: Request, error: ThreadNotFound) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        return JSONResponse({"errors": [f"no thread '{error.args[0]}'"]}, status_code=404)

    @app.exception_handler(BlankComment)
    async def blank(_: Request, error: BlankComment) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        return JSONResponse({"errors": [str(error)]}, status_code=422)

    # comments.json sits next to the plan it comments on.
    store = ThreadStore(plan_file.parent / "comments.json")
    app.include_router(thread_routes(store, plan_file, events))
    app.include_router(approval_routes(store, plan_file, events))

    # Mounted last so /api routes win; html=True serves index.html at "/".
    app.mount("/", StaticFiles(directory=static_dir, html=True))
    return app
