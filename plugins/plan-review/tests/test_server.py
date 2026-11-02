import hashlib
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
from plan_review.threads import ThreadStore

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


def test_owner_can_create_list_reply_resolve_and_reopen_threads(
    plan_file: Path, static_dir: Path
) -> None:
    client = TestClient(create_app(plan_file, static_dir))

    created = client.post("/api/threads", json={"anchor": "class:HintPolicy", "text": "Why?"})
    thread_id = created.json()["id"]
    client.post(f"/api/threads/{thread_id}/replies", json={"text": "More detail"})
    client.post(f"/api/threads/{thread_id}/resolve")
    client.post(f"/api/threads/{thread_id}/reopen")
    listed = client.get("/api/threads").json()["threads"]

    assert created.status_code == 201
    assert len(listed) == 1
    assert [(m["author"], m["text"]) for m in listed[0]["messages"]] == [
        ("owner", "Why?"),
        ("owner", "More detail"),
    ]
    assert listed[0]["resolved"] is False
    assert listed[0]["orphaned"] is False


def test_reply_to_unknown_thread_is_404(plan_file: Path, static_dir: Path) -> None:
    client = TestClient(create_app(plan_file, static_dir))

    response = client.post("/api/threads/t-nope/replies", json={"text": "hi"})

    assert response.status_code == 404
    assert response.json() == {"errors": ["no thread 't-nope'"]}


def test_blank_comment_is_422(plan_file: Path, static_dir: Path) -> None:
    client = TestClient(create_app(plan_file, static_dir))

    response = client.post("/api/threads", json={"anchor": "risk:1", "text": "  "})

    assert response.status_code == 422
    assert response.json() == {"errors": ["comment text is empty"]}


def test_thread_on_an_element_removed_from_the_plan_is_listed_as_orphaned(
    plan_file: Path, static_dir: Path
) -> None:
    client = TestClient(create_app(plan_file, static_dir))
    client.post("/api/threads", json={"anchor": "class:Gone", "text": "?"})

    (thread,) = client.get("/api/threads").json()["threads"]

    assert thread["orphaned"] is True


def test_owners_new_thread_is_announced_on_events(plan_file: Path, static_dir: Path) -> None:
    with (
        TestClient(create_app(plan_file, static_dir)) as client,
        client.websocket_connect("/events") as events,
    ):
        thread = client.post("/api/threads", json={"anchor": "risk:1", "text": "Agree?"}).json()

        assert events.receive_json() == {
            "type": "comment",
            "thread_id": thread["id"],
            "anchor": "risk:1",
            "text": "Agree?",
        }


def test_owner_replies_are_announced_but_claudes_are_not(plan_file: Path, static_dir: Path) -> None:
    store = ThreadStore(plan_file.parent / "comments.json")
    thread = store.create("risk:1", "Agree?")
    with (
        TestClient(create_app(plan_file, static_dir)) as client,
        client.websocket_connect("/events") as events,
    ):
        store.reply(thread.id, "Yes, see mitigation.", author="claude")  # as the CLI does
        client.post(f"/api/threads/{thread.id}/replies", json={"text": "Thanks"})

        assert events.receive_json() == {
            "type": "reply",
            "thread_id": thread.id,
            "anchor": "risk:1",
            "text": "Thanks",
        }


def test_approve_is_refused_while_a_thread_is_unresolved(plan_file: Path, static_dir: Path) -> None:
    ThreadStore(plan_file.parent / "comments.json").create("risk:1", "Open question")
    client = TestClient(create_app(plan_file, static_dir))

    response = client.post("/api/approve")

    assert response.status_code == 409
    assert response.json() == {"errors": ["1 unresolved thread(s): resolve them first"]}
    assert not (plan_file.parent / "approved.json").exists()


def test_approve_records_approval_and_announces_it(plan_file: Path, static_dir: Path) -> None:
    store = ThreadStore(plan_file.parent / "comments.json")
    store.set_resolved(store.create("risk:1", "Q").id, True)
    with (
        TestClient(create_app(plan_file, static_dir)) as client,
        client.websocket_connect("/events") as events,
    ):
        response = client.post("/api/approve")

        assert response.status_code == 200
        assert events.receive_json() == {"type": "approved"}
    record = json.loads((plan_file.parent / "approved.json").read_text())
    assert record["plan_sha256"] == hashlib.sha256(plan_file.read_bytes()).hexdigest()
    assert "approved_at" in record


def test_approve_is_refused_for_an_invalid_plan(plan_file: Path, static_dir: Path) -> None:
    plan_file.write_text("{}")
    client = TestClient(create_app(plan_file, static_dir))

    response = client.post("/api/approve")

    assert response.status_code == 422
    assert not (plan_file.parent / "approved.json").exists()
