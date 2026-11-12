import json
import shutil
import threading
import time
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from plan_review.utils import file_lock
from plan_review.viewer import lifetime
from plan_review.viewer.app import create_app
from plan_review.viewer.lifetime import IdleWatch, ViewerLifetime
from plan_review.viewer.record import ViewerRecord

EXAMPLE = Path(__file__).parents[2] / "examples" / "plan.json"
HOUR = 3600.0


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


def viewer(plan_file: Path, stops: Stops, **options: float) -> ViewerLifetime:
    return ViewerLifetime(
        run_id=plan_file.parent.name,
        token="secret",
        request_stop=stops,
        record=ViewerRecord(plan_file.parent),
        **options,
    )


def detached_app(plan_file: Path, static_dir: Path, lifetime: ViewerLifetime) -> FastAPI:
    """What viewer-process builds: the app with the lifetime's routes and watching plugged in."""
    return create_app(
        plan_file, static_dir, routers=[lifetime.routes()], while_serving=lifetime.watching
    )


def test_an_idle_detached_app_stops_itself(plan_file: Path, static_dir: Path) -> None:
    stops = Stops()
    detached = viewer(plan_file, stops, idle_limit=0.05, check_every=0.01)

    with TestClient(detached_app(plan_file, static_dir, detached)):
        assert stops.asked.wait(timeout=5)
        time.sleep(0.1)  # many checks later
    assert stops.count == 1


def test_viewer_route_says_which_run_it_is(plan_file: Path, static_dir: Path) -> None:
    app = detached_app(plan_file, static_dir, viewer(plan_file, Stops()))

    reply = TestClient(app).get("/api/viewer").json()

    assert reply["run_id"] == "42"
    assert isinstance(reply["pid"], int)


def test_stop_route_refuses_a_wrong_token(plan_file: Path, static_dir: Path) -> None:
    stops = Stops()
    client = TestClient(detached_app(plan_file, static_dir, viewer(plan_file, stops)))

    response = client.post("/api/stop", headers={"x-plan-review-token": "wrong"})

    assert response.status_code == 403
    assert not stops.asked.is_set()


def test_stop_route_with_the_token_stops_the_viewer(plan_file: Path, static_dir: Path) -> None:
    stops = Stops()
    client = TestClient(detached_app(plan_file, static_dir, viewer(plan_file, stops)))

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

    with TestClient(detached_app(plan_file, static_dir, detached)):
        assert record.exists()

    assert not record.exists()


def test_a_viewer_leaves_a_newer_viewers_record_alone(plan_file: Path, static_dir: Path) -> None:
    record = plan_file.parent / "viewer.json"
    record.write_text(json.dumps({"token": "someone else"}))

    with TestClient(detached_app(plan_file, static_dir, viewer(plan_file, Stops()))):
        pass

    assert json.loads(record.read_text()) == {"token": "someone else"}


def test_a_viewer_ending_during_a_start_or_stop_leaves_the_record_to_it(
    plan_file: Path, static_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(lifetime, "RECORD_LOCK_WAIT", 0.05)
    record = plan_file.parent / "viewer.json"
    record.write_text(json.dumps({"token": "secret"}))

    with file_lock(record):  # a start or a stop is under way
        with TestClient(detached_app(plan_file, static_dir, viewer(plan_file, Stops()))):
            pass
        assert record.exists(), "the record was removed while another process held its lock"


@pytest.mark.parametrize("content", ["{ not json", "[]"])
def test_a_viewer_removes_a_record_it_cannot_read(
    plan_file: Path, static_dir: Path, content: str
) -> None:
    record = plan_file.parent / "viewer.json"
    record.write_text(content)

    with TestClient(detached_app(plan_file, static_dir, viewer(plan_file, Stops()))):
        pass

    assert not record.exists()


def test_an_open_page_keeps_the_detached_viewer_running(plan_file: Path, static_dir: Path) -> None:
    stops = Stops()
    detached = viewer(plan_file, stops, idle_limit=0.05, check_every=0.01)

    with TestClient(detached_app(plan_file, static_dir, detached)) as client:
        with client.websocket_connect("/api/updates"):
            time.sleep(0.3)  # many times the limit
            assert not stops.asked.is_set()
        assert stops.asked.wait(timeout=5)  # the page closed: the limit runs from now
