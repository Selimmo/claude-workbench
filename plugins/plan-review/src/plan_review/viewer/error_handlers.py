"""How errors look on the web: each domain error becomes a status code and an errors list."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from plan_review.grill.state import GrillError
from plan_review.plan.plan_file import PlanFileError
from plan_review.review.drafts import DraftNotFound
from plan_review.review.threads import ResolveRefused, ThreadNotFound
from plan_review.utils.json_files import BrokenFile
from plan_review.utils.text import BlankComment


def add_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ThreadNotFound)
    async def not_found(_: Request, error: ThreadNotFound) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        return JSONResponse({"errors": [f"no thread '{error.args[0]}'"]}, status_code=404)

    @app.exception_handler(ResolveRefused)
    async def resolve_refused(_: Request, error: ResolveRefused) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        return JSONResponse({"errors": [str(error)]}, status_code=409)

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

    @app.exception_handler(PlanFileError)
    async def plan_file(_: Request, error: PlanFileError) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        return JSONResponse({"errors": error.errors}, status_code=404 if error.missing else 422)
