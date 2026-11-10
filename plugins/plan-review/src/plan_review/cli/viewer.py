"""How the viewer is started and stopped: serve, stop and the detached viewer-process."""

import socket
import sys
from pathlib import Path

import uvicorn

from plan_review.cli.runtime import Runtime
from plan_review.cli.settings import pipeline_settings, print_hint
from plan_review.paths.run_id import label
from plan_review.paths.run_paths import RunPaths
from plan_review.plan.plan import PlanFileError
from plan_review.settings.pipeline_config import PipelineConfigError
from plan_review.viewer.app import create_app
from plan_review.viewer.detach import (
    DetachedViewer,
    ViewerFailed,
    record_file,
    start_viewer,
    stop_viewer,
)
from plan_review.viewer.start_page import start_page


def serve(run_id: str, open_flag: str | None, *, detach: bool, runtime: Runtime) -> int:
    hint = None
    try:
        if open_flag:
            open_mode = open_flag  # the flag wins, so a broken config doesn't matter
        else:
            config, hint = pipeline_settings()
            open_mode = config.viewer.open
    except PipelineConfigError as error:
        print("\n".join(error.errors), file=sys.stderr)
        return 1
    static_dir = runtime.static_dir
    if not (static_dir / "index.html").is_file():
        print(
            f"{static_dir.as_posix()}: viewer page not built; run `npm --prefix web run build`",
            file=sys.stderr,
        )
        return 2
    paths = RunPaths(runtime.work_dir(Path(), run_id))
    try:
        page = start_page(paths)
    except PlanFileError as error:
        print("\n".join(error.errors), file=sys.stderr)
        return 2 if error.missing else 1
    work = runtime.ensure_work_dir(Path(), run_id)  # the page writes comments and drafts there
    if detach:
        return _serve_detached(run_id, work, page, open_mode, hint, runtime=runtime)
    # Bind and listen before opening the browser: its first request then waits in the
    # socket's queue until uvicorn accepts it, instead of racing the server's startup.
    # Port 0 lets the OS pick a free port.
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen()
        url = f"http://127.0.0.1:{sock.getsockname()[1]}/{page}"
        print(f"plan-review: {label(run_id)} at {url} (Ctrl+C to stop)", flush=True)
        print_hint(hint)  # after the URL line: /ship reads the first line of the output
        if open_mode == "browser":
            runtime.open_browser(url)
        runtime.run_server(create_app(paths.plan, static_dir), sock)
    return 0


def _serve_detached(
    run_id: str, work: Path, page: str, open_mode: str, hint: str | None, *, runtime: Runtime
) -> int:
    try:
        record, started = start_viewer(Path(), work, run_id)
    except ViewerFailed as error:
        print(error.log, file=sys.stderr, end="" if error.log.endswith("\n") else "\n")
        return error.code
    url = f"http://127.0.0.1:{record.port}/{page}"
    print(
        f"plan-review: {label(run_id)} at {url} (stop it with `plan-review stop {run_id}`)",
        flush=True,
    )
    print_hint(hint)
    if started and open_mode == "browser":
        runtime.open_browser(url)
    return 0


def stop(run_id: str, *, runtime: Runtime) -> int:
    if stop_viewer(runtime.work_dir(Path(), run_id), run_id):
        print(f"plan-review: stopped the viewer for {label(run_id)}")
    else:
        print(f"plan-review: no viewer is running for {label(run_id)}")
    return 0


def viewer_process(run_id: str, port: int, token: str, *, runtime: Runtime) -> int:
    """The detached viewer itself: the server of `serve`, stoppable and stopping when idle."""
    work = runtime.work_dir(Path(), run_id)
    server: uvicorn.Server | None = None

    def request_stop() -> None:
        if server is not None:
            server.should_exit = True

    detached = DetachedViewer(
        run_id=run_id, token=token, request_stop=request_stop, record=record_file(work)
    )
    app = create_app(RunPaths(work).plan, runtime.static_dir, detached=detached)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", port))
        sock.listen()
        server = uvicorn.Server(uvicorn.Config(app, log_level="warning"))
        server.run(sockets=[sock])
    return 0
