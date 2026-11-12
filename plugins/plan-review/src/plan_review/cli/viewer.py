"""How the viewer is started and stopped: serve, stop and the detached viewer-process."""

import socket
import sys
from pathlib import Path

from plan_review.cli.runtime import Runtime, ServerStop
from plan_review.cli.settings import pipeline_settings, print_hint
from plan_review.paths.run_id import label
from plan_review.paths.run_paths import RunPaths
from plan_review.plan.plan_file import PlanFileError
from plan_review.settings.pipeline_config import PipelineConfigError
from plan_review.viewer.app import create_app
from plan_review.viewer.launcher import ViewerFailed, ViewerLauncher
from plan_review.viewer.lifetime import ViewerLifetime
from plan_review.viewer.record import ViewerRecord
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
    with _bind_local() as sock:
        url = _url(sock.getsockname()[1], page)
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
        info, started = ViewerLauncher(work, run_id).start(Path())
    except ViewerFailed as error:
        print(error.log, file=sys.stderr, end="" if error.log.endswith("\n") else "\n")
        return error.code
    url = _url(info.port, page)
    print(
        f"plan-review: {label(run_id)} at {url} (stop it with `plan-review stop {run_id}`)",
        flush=True,
    )
    print_hint(hint)
    if started and open_mode == "browser":
        runtime.open_browser(url)
    return 0


def stop(run_id: str, *, runtime: Runtime) -> int:
    if ViewerLauncher(runtime.work_dir(Path(), run_id), run_id).stop():
        print(f"plan-review: stopped the viewer for {label(run_id)}")
    else:
        print(f"plan-review: no viewer is running for {label(run_id)}")
    return 0


def viewer_process(run_id: str, port: int, token: str, *, runtime: Runtime) -> int:
    """The detached viewer itself: the server of `serve`, stoppable and stopping when idle."""
    work = runtime.work_dir(Path(), run_id)
    stop = ServerStop()
    lifetime = ViewerLifetime(
        run_id=run_id, token=token, request_stop=stop, record=ViewerRecord(work)
    )
    app = create_app(
        RunPaths(work).plan,
        runtime.static_dir,
        routers=[lifetime.routes()],
        while_serving=lifetime.watching,
    )
    with _bind_local(port) as sock:
        lifetime.announce(sock.getsockname()[1])  # the launcher waits for this record
        runtime.run_server(app, sock, stop)
    return 0


def _bind_local(port: int = 0) -> socket.socket:
    """A socket on 127.0.0.1, bound and listening. Port 0 lets the OS pick a free port."""
    sock = socket.socket()
    try:
        sock.bind(("127.0.0.1", port))
        sock.listen()
    except BaseException:
        sock.close()
        raise
    return sock


def _url(port: int, page: str) -> str:
    return f"http://127.0.0.1:{port}/{page}"
