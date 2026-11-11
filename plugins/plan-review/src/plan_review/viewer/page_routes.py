"""How the page is served: the HTML, the plan it shows, and the built static files."""

from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from plan_review.plan.plan import load_plan


def serve_page(app: FastAPI, plan_file: Path, static_dir: Path) -> None:
    """Add the page routes. Call it last: the static mount at "/" would catch any later route."""

    @app.get("/grill", response_model=None)
    def grill_page() -> FileResponse:  # pyright: ignore[reportUnusedFunction]
        return FileResponse(static_dir / "index.html")

    @app.get("/", response_model=None)
    def root() -> FileResponse | RedirectResponse:  # pyright: ignore[reportUnusedFunction]
        # Before there is a plan, the grill is the page to look at.
        if not plan_file.exists():
            return RedirectResponse("/grill")
        return FileResponse(static_dir / "index.html")

    @app.get("/api/plan")
    def get_plan() -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        plan = load_plan(plan_file)  # a PlanFileError becomes a 404 or 422 in error_handlers
        return JSONResponse(plan.model_dump(mode="json", by_alias=True))

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
