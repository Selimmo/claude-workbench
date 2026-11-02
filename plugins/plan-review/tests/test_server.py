import json
import shutil
import socket
import threading
from pathlib import Path

import pytest
import uvicorn
from fastapi.testclient import TestClient
from websockets.sync.client import connect

from plan_review.server import create_app

EXAMPLE = Path(__file__).parents[1] / "examples" / "plan.json"


@pytest.fixture
def plan_file(tmp_path: Path) -> Path:
    path = tmp_path / ".claude" / "work" / "42" / "plan.json"
    path.parent.mkdir(parents=True)
    shutil.copy(EXAMPLE, path)
    return path


@pytest.fixture
def static_dir(tmp_path: Path) -> Path:
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<h1>plan-review</h1>")
    return static


def test_api_plan_returns_the_plan_with_json_field_names(plan_file: Path, static_dir: Path) -> None:
    client = TestClient(create_app(plan_file, static_dir))

    response = client.get("/api/plan")

    assert response.status_code == 200
    assert response.json()["issue"]["number"] == 42
    assert response.json()["relations"][0]["from"] == "class:Orchestrator"


def test_api_plan_missing_file_is_404_naming_the_path(plan_file: Path, static_dir: Path) -> None:
    plan_file.unlink()
    client = TestClient(create_app(plan_file, static_dir))

    response = client.get("/api/plan")

    assert response.status_code == 404
    assert response.json() == {"errors": [f"{plan_file}: file not found"]}


def test_api_plan_invalid_file_is_422_with_readable_errors(
    plan_file: Path, static_dir: Path
) -> None:
    plan_file.write_text(json.dumps({"issue": {"number": 1, "title": "x"}}))
    client = TestClient(create_app(plan_file, static_dir))

    response = client.get("/api/plan")

    assert response.status_code == 422
    assert response.json() == {"errors": ["summary: Field required"]}


def test_root_serves_the_built_page(plan_file: Path, static_dir: Path) -> None:
    client = TestClient(create_app(plan_file, static_dir))

    response = client.get("/")

    assert response.status_code == 200
    assert "<h1>plan-review</h1>" in response.text


def test_connected_pages_are_told_when_the_plan_file_changes(
    plan_file: Path, static_dir: Path
) -> None:
    app = create_app(plan_file, static_dir, poll_interval=0.01)

    with TestClient(app) as client, client.websocket_connect("/api/updates") as updates:
        plan_file.write_text(plan_file.read_text() + "\n")

        assert updates.receive_json() == {"type": "plan_changed"}


def test_real_uvicorn_server_pushes_plan_changes_over_websocket(
    plan_file: Path, static_dir: Path
) -> None:
    # TestClient bypasses uvicorn, so it cannot catch a missing WebSocket library.
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen()
    port = sock.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(create_app(plan_file, static_dir, poll_interval=0.01), log_level="error")
    )
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    try:
        with connect(f"ws://127.0.0.1:{port}/api/updates", open_timeout=5) as updates:
            plan_file.write_text(plan_file.read_text() + "\n")
            assert json.loads(updates.recv(timeout=5)) == {"type": "plan_changed"}
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        sock.close()
