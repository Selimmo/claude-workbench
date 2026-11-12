import json
import os
import shutil
import subprocess
import sys
import threading
import urllib.request
from pathlib import Path

import pytest

from plan_review.cli import main
from plan_review.cli.runtime import Runtime
from plan_review.utils import file_lock
from plan_review.viewer import launcher
from plan_review.viewer.client import ViewerClient
from plan_review.viewer.launcher import ProcessSpawner, ViewerFailed, ViewerLauncher
from plan_review.viewer.record import ViewerInfo, ViewerRecord

EXAMPLE = Path(__file__).parents[2] / "examples" / "plan.json"
NEWER_RECORD = {"run_id": "7", "pid": 9, "port": 1, "token": "newer"}


class FakeProcess:
    def __init__(
        self,
        pid: int,
        code: int | None = None,
        record: Path | None = None,
        writes_on_poll: tuple[int, str, Path] | None = None,
    ) -> None:
        self.pid = pid
        self.writes_on_poll = writes_on_poll
        self.code = code
        self.record = record
        self.killed_with_record: bool | None = None

    def poll(self) -> int | None:
        if self.writes_on_poll is not None:
            port, token, log = self.writes_on_poll
            self.writes_on_poll = None
            ViewerRecord(log.parent).write(
                ViewerInfo(run_id="7", pid=self.pid, port=port, token=token)
            )
        return self.code

    def kill(self) -> None:
        self.killed_with_record = self.record is not None and self.record.exists()


class FakeViewers:
    """Stands in for spawning a process and asking it who it is."""

    def __init__(self, static_dir: Path) -> None:
        self.opened: list[str] = []
        self.runtime = Runtime(static_dir=static_dir, open_browser=self.opened.append)
        self.spawned: list[tuple[str, str]] = []
        self.last: FakeProcess | None = None
        self.alive: dict[int, str] = {}  # port -> the run it answers as
        self.crash_with: int | None = None
        self.never_answers = False
        self.late_viewer_first = False  # an older viewer's record shows up before our own
        self.silent_log = b""  # what a viewer that never answers writes to its log
        self.ignores_stop = False
        self.removes_record_on_stop = False
        self.replaced_on_stop: Path | None = None  # a new viewer takes this record over
        self.crash_log = b"Traceback: could not start\n"
        self.stopped: list[tuple[int, str]] = []
        self.records: list[Path] = []

    def spawn(self, root: Path, run_id: str, token: str, log: Path) -> FakeProcess:
        self.spawned.append((run_id, token))
        if self.crash_with is not None:
            log.write_bytes(self.crash_log)
            self.last = FakeProcess(7000, self.crash_with)
            return self.last
        chosen = 54320 + len(self.spawned)  # the viewer picks its own port, and says so
        if self.late_viewer_first:
            self.alive[1] = run_id  # a port that answers as this run, but is not ours
            ViewerRecord(log.parent).write(ViewerInfo(run_id=run_id, pid=9, port=1, token="older"))
            self.alive[chosen] = run_id
            self.last = FakeProcess(7000 + len(self.spawned), writes_on_poll=(chosen, token, log))
            return self.last
        ViewerRecord(log.parent).write(
            ViewerInfo(run_id=run_id, pid=7000 + len(self.spawned), port=chosen, token=token)
        )
        if self.never_answers:
            log.write_bytes(self.silent_log)
        else:
            self.alive[chosen] = run_id
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
            with file_lock(self.replaced_on_stop):  # as ViewerLauncher.start writes it
                self.replaced_on_stop.write_text(json.dumps(NEWER_RECORD))


@pytest.fixture
def viewers(project: Path, monkeypatch: pytest.MonkeyPatch) -> FakeViewers:
    fake = FakeViewers(project / "static")
    monkeypatch.setattr(ProcessSpawner, "spawn", fake.spawn)
    monkeypatch.setattr(ViewerClient, "answers_as", fake.probe)
    monkeypatch.setattr(ViewerClient, "post_stop", fake.post_stop)
    monkeypatch.setattr(launcher, "READY_POLL", 0.01)
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
    return tmp_path


def record_of(project: Path, run_id: str = "7") -> dict[str, object]:
    return json.loads((project / ".plan-review" / "work" / run_id / "viewer.json").read_text())


def first_line(capsys: pytest.CaptureFixture[str]) -> str:
    return capsys.readouterr().out.splitlines()[0]


def test_serve_detach_starts_one_viewer_and_prints_its_url(
    project: Path, viewers: FakeViewers, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(["serve", "7", "--detach"], runtime=viewers.runtime)

    port = record_of(project)["port"]
    assert exit_code == 0
    assert first_line(capsys).startswith(f"plan-review: #7 at http://127.0.0.1:{port}/")
    assert len(viewers.spawned) == 1
    assert viewers.opened == [f"http://127.0.0.1:{port}/"]


def test_serve_detach_prints_the_port_the_viewer_chose(
    project: Path, viewers: FakeViewers, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(["serve", "7", "--detach", "--open", "none"], runtime=viewers.runtime)

    assert exit_code == 0
    assert first_line(capsys) == (
        "plan-review: #7 at http://127.0.0.1:54321/ (stop it with `plan-review stop 7`)"
    )
    assert record_of(project)["port"] == 54321


def test_the_viewer_is_started_with_port_0() -> None:
    assert ProcessSpawner().command("7", "t") == [
        sys.executable,
        "-m",
        "plan_review.cli",
        "viewer-process",
        "7",
        "--port",
        "0",
        "--token",
        "t",
    ]


def test_serve_detach_hints_on_stderr_after_the_url(
    project: Path, viewers: FakeViewers, capsys: pytest.CaptureFixture[str]
) -> None:
    old = project / ".claude" / "pipeline.json"
    old.parent.mkdir()
    old.write_text(json.dumps({"max_review_rounds": 4}))

    assert main(["serve", "7", "--detach"], runtime=viewers.runtime) == 0

    out, err = capsys.readouterr()
    assert out.splitlines()[0].startswith("plan-review: #7 at http://")
    assert ".plan-review/config.json" not in out
    assert ".plan-review/config.json" in err


def test_serve_detach_reuses_a_viewer_already_running(
    project: Path, viewers: FakeViewers, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["serve", "7", "--detach"], runtime=viewers.runtime)
    first = first_line(capsys)
    viewers.opened.clear()

    exit_code = main(["serve", "7", "--detach"], runtime=viewers.runtime)

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

    assert main(["serve", "9", "--detach", "--open", "none"], runtime=viewers.runtime) == 0

    url = first_line(capsys).split(" at ")[1].split(" ")[0]
    assert url == f"http://127.0.0.1:{record_of(project, '9')['port']}/grill"


def test_serve_detach_replaces_a_stale_record(project: Path, viewers: FakeViewers) -> None:
    main(["serve", "7", "--detach"], runtime=viewers.runtime)
    viewers.alive.clear()  # the process is gone

    viewers.opened.clear()

    assert main(["serve", "7", "--detach", "--open", "none"], runtime=viewers.runtime) == 0

    assert len(viewers.spawned) == 2
    assert viewers.opened == []


def test_a_failed_start_clears_an_old_record_too(project: Path, viewers: FakeViewers) -> None:
    main(["serve", "7", "--detach"], runtime=viewers.runtime)
    viewers.alive.clear()  # the old viewer is gone, its record is left
    viewers.crash_with = 3

    assert main(["serve", "7", "--detach"], runtime=viewers.runtime) == 3

    assert not (project / ".plan-review" / "work" / "7" / "viewer.json").exists()


def test_start_waits_for_a_record_carrying_its_own_token(
    project: Path, viewers: FakeViewers
) -> None:
    viewers.late_viewer_first = True
    work = project / ".plan-review" / "work" / "7"

    info, started = ViewerLauncher(work, "7").start(project)

    assert started is True
    assert info.token == viewers.spawned[0][1]
    assert info.port != 1


def test_a_viewer_that_never_answers_is_given_up_on(
    project: Path, viewers: FakeViewers, monkeypatch: pytest.MonkeyPatch
) -> None:
    viewers.never_answers = True  # alive, but silent
    monkeypatch.setattr(launcher, "READY_TIMEOUT", 0.05)
    work = project / ".plan-review" / "work" / "7"

    with pytest.raises(ViewerFailed) as error:
        ViewerLauncher(work, "7").start(project)

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
    monkeypatch.setattr(launcher, "READY_TIMEOUT", 0.05)

    assert main(["serve", "7", "--detach"], runtime=viewers.runtime) == 1

    lines = capsys.readouterr().err.splitlines()
    assert "did not answer within" in lines[0]
    assert lines[1] == "WARNING: slow disk"


def test_two_starts_at_once_make_one_viewer(project: Path, viewers: FakeViewers) -> None:
    work = project / ".plan-review" / "work" / "7"
    results: list[tuple[int, bool]] = []

    def start() -> None:
        record, started = ViewerLauncher(work, "7").start(project)
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

    exit_code = main(["serve", "7", "--detach"], runtime=viewers.runtime)

    assert exit_code == 3
    assert capsys.readouterr().err == "Traceback: could not start\n"
    assert not (project / ".plan-review" / "work" / "7" / "viewer.json").exists()


def test_each_run_gets_its_own_viewer(project: Path, viewers: FakeViewers) -> None:
    main(["serve", "7", "--detach"], runtime=viewers.runtime)
    main(["serve", "8", "--detach"], runtime=viewers.runtime)

    assert record_of(project, "7")["port"] != record_of(project, "8")["port"]
    assert len(viewers.spawned) == 2


def test_stop_ends_the_viewer_and_clears_the_record(project: Path, viewers: FakeViewers) -> None:
    main(["serve", "7", "--detach"], runtime=viewers.runtime)
    token = record_of(project)["token"]

    exit_code = main(["stop", "7"])

    assert exit_code == 0
    assert [t for _, t in viewers.stopped] == [token]
    assert not (project / ".plan-review" / "work" / "7" / "viewer.json").exists()


def test_stop_gives_up_on_a_viewer_that_will_not_stop(
    project: Path, viewers: FakeViewers, monkeypatch: pytest.MonkeyPatch
) -> None:
    main(["serve", "7", "--detach"], runtime=viewers.runtime)
    viewers.ignores_stop = True
    monkeypatch.setattr(launcher, "READY_TIMEOUT", 0.05)

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
    main(["serve", "7", "--detach"], runtime=viewers.runtime)
    viewers.alive.clear()

    assert main(["stop", "7"]) == 0

    assert viewers.stopped == []  # no token sent to a port that doesn't answer as this run
    assert not (project / ".plan-review" / "work" / "7" / "viewer.json").exists()


def test_stop_leaves_a_newer_viewers_record_alone(project: Path, viewers: FakeViewers) -> None:
    main(["serve", "7", "--detach"], runtime=viewers.runtime)
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
        ViewerLauncher(work, "7").stop()  # never leave a viewer running after a failure


def test_stop_copes_with_the_viewer_removing_its_own_record(
    project: Path, viewers: FakeViewers
) -> None:
    main(["serve", "7", "--detach"], runtime=viewers.runtime)
    viewers.records.append(project / ".plan-review" / "work" / "7" / "viewer.json")
    viewers.removes_record_on_stop = True

    assert main(["stop", "7"]) == 0


def test_a_viewer_that_already_crashed_is_not_killed(project: Path, viewers: FakeViewers) -> None:
    viewers.crash_with = 3

    assert main(["serve", "7", "--detach"], runtime=viewers.runtime) == 3

    assert viewers.last is not None
    assert viewers.last.killed_with_record is None


def test_a_crash_log_that_is_not_text_is_still_reported(
    project: Path, viewers: FakeViewers, capsys: pytest.CaptureFixture[str]
) -> None:
    viewers.crash_with = 3
    viewers.crash_log = b"bad \xff byte"

    assert main(["serve", "7", "--detach"], runtime=viewers.runtime) == 3

    assert capsys.readouterr().err == "bad \ufffd byte\n"
