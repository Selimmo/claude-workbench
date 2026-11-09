import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from plan_review import cli, detach
from plan_review.cli import main
from plan_review.detach import DetachedViewer, IdleWatch, ViewerFailed
from plan_review.server import create_app
from plan_review.threads import file_lock

EXAMPLE = Path(__file__).parents[1] / "examples" / "plan.json"
HOUR = 3600.0
NEWER_RECORD = {"run_id": "7", "pid": 9, "port": 1, "token": "newer"}


def test_viewer_never_opened_stops_two_hours_after_starting() -> None:
    watch = IdleWatch(started=0.0)

    assert not watch.expired(0, now=2 * HOUR - 60)
    assert watch.expired(0, now=2 * HOUR)


def test_an_open_page_keeps_the_viewer_running_however_long() -> None:
    watch = IdleWatch(started=0.0)

    assert not watch.expired(1, now=1.0)
    assert not watch.expired(1, now=100 * HOUR)


def test_viewer_stops_two_hours_after_the_page_closes() -> None:
    watch = IdleWatch(started=0.0)
    watch.expired(1, now=10 * HOUR)

    assert not watch.expired(0, now=10 * HOUR)  # closed just now
    assert not watch.expired(0, now=12 * HOUR - 60)
    assert watch.expired(0, now=12 * HOUR)


def test_coming_back_resets_the_two_hours() -> None:
    watch = IdleWatch(started=0.0)
    watch.expired(1, now=0.0)
    watch.expired(0, now=HOUR)  # closed at 1h
    watch.expired(1, now=2 * HOUR)  # back at 2h
    watch.expired(0, now=3 * HOUR)  # closed again at 3h

    assert not watch.expired(0, now=5 * HOUR - 60)
    assert watch.expired(0, now=5 * HOUR)


@pytest.fixture
def plan_file(tmp_path: Path) -> Path:
    path = tmp_path / ".plan-review" / "work" / "42" / "plan.json"
    path.parent.mkdir(parents=True)
    shutil.copy(EXAMPLE, path)
    return path


@pytest.fixture
def static_dir(tmp_path: Path) -> Path:
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<h1>plan-review</h1>")
    return static


class Stops:
    def __init__(self) -> None:
        self.asked = threading.Event()
        self.count = 0

    def __call__(self) -> None:
        self.count += 1
        self.asked.set()


def viewer(plan_file: Path, stops: Stops, **options: float) -> DetachedViewer:
    return DetachedViewer(
        run_id=plan_file.parent.name,
        token="secret",
        request_stop=stops,
        record=plan_file.parent / "viewer.json",
        **options,
    )


def test_an_idle_detached_app_stops_itself(plan_file: Path, static_dir: Path) -> None:
    stops = Stops()
    detached = viewer(plan_file, stops, idle_limit=0.05, check_every=0.01)

    with TestClient(create_app(plan_file, static_dir, detached=detached)):
        assert stops.asked.wait(timeout=5)
        time.sleep(0.1)  # many checks later
    assert stops.count == 1


def test_viewer_route_says_which_run_it_is(plan_file: Path, static_dir: Path) -> None:
    app = create_app(plan_file, static_dir, detached=viewer(plan_file, Stops()))

    reply = TestClient(app).get("/api/viewer").json()

    assert reply["run_id"] == "42"
    assert isinstance(reply["pid"], int)


def test_stop_route_refuses_a_wrong_token(plan_file: Path, static_dir: Path) -> None:
    stops = Stops()
    client = TestClient(create_app(plan_file, static_dir, detached=viewer(plan_file, stops)))

    response = client.post("/api/stop", headers={"x-plan-review-token": "wrong"})

    assert response.status_code == 403
    assert not stops.asked.is_set()


def test_stop_route_with_the_token_stops_the_viewer(plan_file: Path, static_dir: Path) -> None:
    stops = Stops()
    client = TestClient(create_app(plan_file, static_dir, detached=viewer(plan_file, stops)))

    response = client.post("/api/stop", headers={"x-plan-review-token": "secret"})

    assert response.status_code == 200
    assert stops.asked.is_set()


def test_a_normal_serve_has_no_stop_route(plan_file: Path, static_dir: Path) -> None:
    client = TestClient(create_app(plan_file, static_dir))

    response = client.post("/api/stop", headers={"x-plan-review-token": "secret"})

    assert response.status_code == 405
    assert client.get("/api/viewer").status_code == 404


def test_a_viewer_removes_its_record_when_it_stops_itself(
    plan_file: Path, static_dir: Path
) -> None:
    record = plan_file.parent / "viewer.json"
    record.write_text(json.dumps({"token": "secret"}))
    detached = viewer(plan_file, Stops())

    with TestClient(create_app(plan_file, static_dir, detached=detached)):
        assert record.exists()

    assert not record.exists()


def test_a_viewer_leaves_a_newer_viewers_record_alone(plan_file: Path, static_dir: Path) -> None:
    record = plan_file.parent / "viewer.json"
    record.write_text(json.dumps({"token": "someone else"}))

    with TestClient(create_app(plan_file, static_dir, detached=viewer(plan_file, Stops()))):
        pass

    assert json.loads(record.read_text()) == {"token": "someone else"}


def test_a_viewer_ending_during_a_start_or_stop_leaves_the_record_to_it(
    plan_file: Path, static_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(detach, "RECORD_LOCK_WAIT", 0.05)
    record = plan_file.parent / "viewer.json"
    record.write_text(json.dumps({"token": "secret"}))

    with file_lock(record):  # a start or a stop is under way
        with TestClient(create_app(plan_file, static_dir, detached=viewer(plan_file, Stops()))):
            pass
        assert record.exists(), "the record was removed while another process held its lock"


@pytest.mark.parametrize("content", ["{ not json", "[]"])
def test_a_viewer_removes_a_record_it_cannot_read(
    plan_file: Path, static_dir: Path, content: str
) -> None:
    record = plan_file.parent / "viewer.json"
    record.write_text(content)

    with TestClient(create_app(plan_file, static_dir, detached=viewer(plan_file, Stops()))):
        pass

    assert not record.exists()


def test_an_open_page_keeps_the_detached_viewer_running(plan_file: Path, static_dir: Path) -> None:
    stops = Stops()
    detached = viewer(plan_file, stops, idle_limit=0.05, check_every=0.01)

    with TestClient(create_app(plan_file, static_dir, detached=detached)) as client:
        with client.websocket_connect("/api/updates"):
            time.sleep(0.3)  # many times the limit
            assert not stops.asked.is_set()
        assert stops.asked.wait(timeout=5)  # the page closed: the limit runs from now


# --- starting and stopping the detached viewer -------------------------------------------


class FakeProcess:
    def __init__(self, pid: int, code: int | None = None, record: Path | None = None) -> None:
        self.pid = pid
        self.code = code
        self.record = record
        self.killed_with_record: bool | None = None

    def poll(self) -> int | None:
        return self.code

    def kill(self) -> None:
        self.killed_with_record = self.record is not None and self.record.exists()


class FakeViewers:
    """Stands in for spawning a process and asking it who it is."""

    def __init__(self) -> None:
        self.spawned: list[tuple[str, int, str]] = []
        self.last: FakeProcess | None = None
        self.alive: dict[int, str] = {}  # port -> the run it answers as
        self.crash_with: int | None = None
        self.never_answers = False
        self.silent_log = b""  # what a viewer that never answers writes to its log
        self.ignores_stop = False
        self.removes_record_on_stop = False
        self.replaced_on_stop: Path | None = None  # a new viewer takes this record over
        self.crash_log = b"Traceback: could not start\n"
        self.stopped: list[tuple[int, str]] = []
        self.opened: list[str] = []
        self.records: list[Path] = []

    def spawn(self, root: Path, run_id: str, port: int, token: str, log: Path) -> FakeProcess:
        self.spawned.append((run_id, port, token))
        if self.crash_with is not None:
            log.write_bytes(self.crash_log)
            self.last = FakeProcess(7000, self.crash_with)
            return self.last
        if self.never_answers:
            log.write_bytes(self.silent_log)
        else:
            self.alive[port] = run_id
        self.last = FakeProcess(7000 + len(self.spawned), record=log.with_name("viewer.json"))
        return self.last

    def probe(self, port: int, run_id: str) -> bool:
        return self.alive.get(port) == run_id

    def post_stop(self, port: int, token: str) -> None:
        self.stopped.append((port, token))
        if not self.ignores_stop:
            self.alive.pop(port, None)
        if self.removes_record_on_stop:
            for record in self.records:
                record.unlink(missing_ok=True)
        if self.replaced_on_stop is not None:
            with file_lock(self.replaced_on_stop):  # as start_viewer writes it
                self.replaced_on_stop.write_text(json.dumps(NEWER_RECORD))


@pytest.fixture
def viewers(monkeypatch: pytest.MonkeyPatch) -> FakeViewers:
    fake = FakeViewers()
    monkeypatch.setattr(detach, "spawn_viewer", fake.spawn)
    monkeypatch.setattr(detach, "answers_as", fake.probe)
    monkeypatch.setattr(detach, "post_stop", fake.post_stop)
    monkeypatch.setattr(detach, "READY_POLL", 0.01)
    monkeypatch.setattr(cli.webbrowser, "open", lambda url: fake.opened.append(url) or True)
    return fake


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    for run_id in ("7", "8"):
        work = tmp_path / ".plan-review" / "work" / run_id
        work.mkdir(parents=True)
        shutil.copy(EXAMPLE, work / "plan.json")
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<h1>plan-review</h1>")
    monkeypatch.setattr(cli, "STATIC_DIR", static)
    return tmp_path


def record_of(project: Path, run_id: str = "7") -> dict[str, object]:
    return json.loads((project / ".plan-review" / "work" / run_id / "viewer.json").read_text())


def first_line(capsys: pytest.CaptureFixture[str]) -> str:
    return capsys.readouterr().out.splitlines()[0]


def test_serve_detach_starts_one_viewer_and_prints_its_url(
    project: Path, viewers: FakeViewers, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(["serve", "7", "--detach"])

    port = record_of(project)["port"]
    assert exit_code == 0
    assert first_line(capsys).startswith(f"plan-review: #7 at http://127.0.0.1:{port}/")
    assert len(viewers.spawned) == 1
    assert viewers.opened == [f"http://127.0.0.1:{port}/"]


def test_serve_detach_hints_on_stderr_after_the_url(
    project: Path, viewers: FakeViewers, capsys: pytest.CaptureFixture[str]
) -> None:
    old = project / ".claude" / "pipeline.json"
    old.parent.mkdir()
    old.write_text(json.dumps({"max_review_rounds": 4}))

    assert main(["serve", "7", "--detach"]) == 0

    out, err = capsys.readouterr()
    assert out.splitlines()[0].startswith("plan-review: #7 at http://")
    assert ".plan-review/config.json" not in out
    assert ".plan-review/config.json" in err


def test_serve_detach_reuses_a_viewer_already_running(
    project: Path, viewers: FakeViewers, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["serve", "7", "--detach"])
    first = first_line(capsys)
    viewers.opened.clear()

    exit_code = main(["serve", "7", "--detach"])

    assert exit_code == 0
    assert first_line(capsys) == first
    assert len(viewers.spawned) == 1
    assert viewers.opened == []


def test_serve_detach_of_a_grill_only_run_prints_the_grill_page(
    project: Path, viewers: FakeViewers, capsys: pytest.CaptureFixture[str]
) -> None:
    run = project / ".plan-review" / "work" / "9"
    run.mkdir()
    (run / "grill.json").write_text("{}")

    assert main(["serve", "9", "--detach", "--open", "none"]) == 0

    url = first_line(capsys).split(" at ")[1].split(" ")[0]
    assert url == f"http://127.0.0.1:{record_of(project, '9')['port']}/grill"


def test_serve_detach_replaces_a_stale_record(project: Path, viewers: FakeViewers) -> None:
    main(["serve", "7", "--detach"])
    viewers.alive.clear()  # the process is gone

    viewers.opened.clear()

    assert main(["serve", "7", "--detach", "--open", "none"]) == 0

    assert len(viewers.spawned) == 2
    assert viewers.opened == []


def serve_body(body: bytes) -> tuple[HTTPServer, int]:
    class Answer(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            self.send_response(200)
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = HTTPServer(("127.0.0.1", 0), Answer)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, server.server_address[1]


def test_a_port_answering_as_another_run_counts_as_stale() -> None:
    server, port = serve_body(json.dumps({"run_id": "other", "pid": 1}).encode())
    try:
        assert detach.answers_as(port, "other")
        assert not detach.answers_as(port, "7")
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.parametrize("body", [b"<h1>some other server</h1>", b"[1, 2]", b'"text"'])
def test_a_port_answering_with_something_else_counts_as_stale(body: bytes) -> None:
    server, port = serve_body(body)
    try:
        assert not detach.answers_as(port, "7")
    finally:
        server.shutdown()
        server.server_close()


def test_a_viewer_that_never_answers_is_given_up_on(
    project: Path, viewers: FakeViewers, monkeypatch: pytest.MonkeyPatch
) -> None:
    viewers.never_answers = True  # alive, but silent
    monkeypatch.setattr(detach, "READY_TIMEOUT", 0.05)
    work = project / ".plan-review" / "work" / "7"

    with pytest.raises(ViewerFailed) as error:
        detach.start_viewer(project, work, "7")

    assert error.value.code == 1
    assert not (work / "viewer.json").exists()
    assert viewers.last is not None
    assert viewers.last.killed_with_record is True  # stopped first, while still findable


def test_a_timeout_says_why_ahead_of_the_viewers_log(
    project: Path,
    viewers: FakeViewers,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    viewers.never_answers = True
    viewers.silent_log = b"WARNING: slow disk\n"
    monkeypatch.setattr(detach, "READY_TIMEOUT", 0.05)

    assert main(["serve", "7", "--detach"]) == 1

    lines = capsys.readouterr().err.splitlines()
    assert "did not answer within" in lines[0]
    assert lines[1] == "WARNING: slow disk"


def test_two_starts_at_once_make_one_viewer(project: Path, viewers: FakeViewers) -> None:
    work = project / ".plan-review" / "work" / "7"
    results: list[tuple[int, bool]] = []

    def start() -> None:
        record, started = detach.start_viewer(project, work, "7")
        results.append((record.port, started))

    threads = [threading.Thread(target=start) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)

    assert len(viewers.spawned) == 1
    assert len({port for port, _ in results}) == 1
    assert sorted(started for _, started in results) == [False, True]


def test_a_viewer_that_fails_to_start_is_reported(
    project: Path, viewers: FakeViewers, capsys: pytest.CaptureFixture[str]
) -> None:
    viewers.crash_with = 3

    exit_code = main(["serve", "7", "--detach"])

    assert exit_code == 3
    assert capsys.readouterr().err == "Traceback: could not start\n"
    assert not (project / ".plan-review" / "work" / "7" / "viewer.json").exists()


def test_each_run_gets_its_own_viewer(project: Path, viewers: FakeViewers) -> None:
    main(["serve", "7", "--detach"])
    main(["serve", "8", "--detach"])

    assert record_of(project, "7")["port"] != record_of(project, "8")["port"]
    assert len(viewers.spawned) == 2


def test_stop_ends_the_viewer_and_clears_the_record(project: Path, viewers: FakeViewers) -> None:
    main(["serve", "7", "--detach"])
    token = record_of(project)["token"]

    exit_code = main(["stop", "7"])

    assert exit_code == 0
    assert [t for _, t in viewers.stopped] == [token]
    assert not (project / ".plan-review" / "work" / "7" / "viewer.json").exists()


def test_stop_gives_up_on_a_viewer_that_will_not_stop(
    project: Path, viewers: FakeViewers, monkeypatch: pytest.MonkeyPatch
) -> None:
    main(["serve", "7", "--detach"])
    viewers.ignores_stop = True
    monkeypatch.setattr(detach, "READY_TIMEOUT", 0.05)

    assert main(["stop", "7"]) == 0

    assert not (project / ".plan-review" / "work" / "7" / "viewer.json").exists()


def test_stop_with_no_viewer_says_so(
    project: Path, viewers: FakeViewers, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(["stop", "7"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert len(out.splitlines()) == 1
    assert "no viewer" in out


def test_stop_with_a_stale_record_clears_it(project: Path, viewers: FakeViewers) -> None:
    main(["serve", "7", "--detach"])
    viewers.alive.clear()

    assert main(["stop", "7"]) == 0

    assert viewers.stopped == []  # no token sent to a port that doesn't answer as this run
    assert not (project / ".plan-review" / "work" / "7" / "viewer.json").exists()


def test_stop_leaves_a_newer_viewers_record_alone(project: Path, viewers: FakeViewers) -> None:
    main(["serve", "7", "--detach"])
    record = project / ".plan-review" / "work" / "7" / "viewer.json"
    viewers.replaced_on_stop = record

    assert main(["stop", "7"]) == 0

    assert record.exists(), "the newer viewer's record was deleted"
    assert json.loads(record.read_text())["token"] == "newer"


@pytest.mark.timeout(90)
def test_a_real_detached_viewer_outlives_its_command_and_stops(tmp_path: Path) -> None:
    work = tmp_path / ".plan-review" / "work" / "7"
    work.mkdir(parents=True)
    shutil.copy(EXAMPLE, work / "plan.json")
    try:
        # a command of its own that ends, as a Codex turn does
        command = subprocess.run(
            [sys.executable, "-m", "plan_review.cli", "serve", "7", "--detach", "--open", "none"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert command.returncode == 0, command.stderr
        url = command.stdout.splitlines()[0].split(" at ")[1].split(" ")[0]

        # the command has ended; the viewer is still there
        with urllib.request.urlopen(f"{url}api/plan", timeout=5) as reply:
            assert reply.status == 200
        if sys.platform != "win32":  # in a session of its own, so closing the turn spares it
            pid = json.loads((work / "viewer.json").read_text())["pid"]
            assert os.getsid(pid) != os.getsid(0)

        stopped = subprocess.run(
            [sys.executable, "-m", "plan_review.cli", "stop", "7"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert stopped.returncode == 0, stopped.stderr
        assert not (work / "viewer.json").exists()
        with pytest.raises(OSError):
            urllib.request.urlopen(f"{url}api/plan", timeout=2)
    finally:
        detach.stop_viewer(work, "7")  # never leave a viewer running after a failure


def test_stop_copes_with_the_viewer_removing_its_own_record(
    project: Path, viewers: FakeViewers
) -> None:
    main(["serve", "7", "--detach"])
    viewers.records.append(project / ".plan-review" / "work" / "7" / "viewer.json")
    viewers.removes_record_on_stop = True

    assert main(["stop", "7"]) == 0


def test_post_stop_does_not_raise_when_nothing_listens() -> None:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    detach.post_stop(port, "token")  # nothing listens now


def test_a_viewer_that_already_crashed_is_not_killed(project: Path, viewers: FakeViewers) -> None:
    viewers.crash_with = 3

    assert main(["serve", "7", "--detach"]) == 3

    assert viewers.last is not None
    assert viewers.last.killed_with_record is None


def test_a_crash_log_that_is_not_text_is_still_reported(
    project: Path, viewers: FakeViewers, capsys: pytest.CaptureFixture[str]
) -> None:
    viewers.crash_with = 3
    viewers.crash_log = b"bad \xff byte"

    assert main(["serve", "7", "--detach"]) == 3

    assert capsys.readouterr().err == "bad \ufffd byte\n"
