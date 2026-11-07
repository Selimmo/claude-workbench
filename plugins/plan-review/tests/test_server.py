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

from plan_review.drafts import DraftStore
from plan_review.server import create_app
from plan_review.status import StatusStore
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
    assert response.json()["relations"][0]["from"] == "class:Orchestrator"


def test_the_api_serves_an_old_plan_in_the_new_form(plan_file: Path, static_dir: Path) -> None:
    old = json.loads(plan_file.read_text())
    del old["issue"]["id"], old["issue"]["kind"]
    old["issue"]["number"] = 42
    plan_file.write_text(json.dumps(old))
    client = TestClient(create_app(plan_file, static_dir))

    issue = client.get("/api/plan").json()["issue"]

    assert (issue["id"], issue["kind"]) == ("42", "issue")
    assert "number" not in issue


def test_api_plan_missing_file_is_404_naming_the_path(plan_file: Path, static_dir: Path) -> None:
    plan_file.unlink()
    client = TestClient(create_app(plan_file, static_dir))

    response = client.get("/api/plan")

    assert response.status_code == 404
    assert response.json() == {"errors": [f"{plan_file.as_posix()}: file not found"]}


def test_api_plan_invalid_file_is_422_with_named_errors(plan_file: Path, static_dir: Path) -> None:
    plan_file.write_text(json.dumps({"issue": {"id": "1", "kind": "issue", "title": "x"}}))
    client = TestClient(create_app(plan_file, static_dir))

    response = client.get("/api/plan")

    assert response.status_code == 422
    assert response.json() == {"errors": [f"{plan_file.as_posix()}: summary: Field required"]}


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


def test_owner_can_list_resolve_and_reopen_threads(plan_file: Path, static_dir: Path) -> None:
    thread = ThreadStore(plan_file.parent / "comments.json").create("class:HintPolicy", "Why?")
    client = TestClient(create_app(plan_file, static_dir))

    client.post(f"/api/threads/{thread.id}/resolve")
    client.post(f"/api/threads/{thread.id}/reopen")
    (listed,) = client.get("/api/threads").json()["threads"]

    assert [(m["author"], m["text"]) for m in listed["messages"]] == [("owner", "Why?")]
    assert listed["resolved"] is False
    assert listed["orphaned"] is False


def test_resolving_an_unknown_thread_is_404(plan_file: Path, static_dir: Path) -> None:
    client = TestClient(create_app(plan_file, static_dir))

    response = client.post("/api/threads/t-nope/resolve")

    assert response.status_code == 404
    assert response.json() == {"errors": ["no thread 't-nope'"]}


def test_thread_on_an_element_removed_from_the_plan_is_listed_as_orphaned(
    plan_file: Path, static_dir: Path
) -> None:
    ThreadStore(plan_file.parent / "comments.json").create("class:Gone", "?")
    client = TestClient(create_app(plan_file, static_dir))

    (thread,) = client.get("/api/threads").json()["threads"]

    assert thread["orphaned"] is True


def test_an_added_draft_is_listed(plan_file: Path, static_dir: Path) -> None:
    client = TestClient(create_app(plan_file, static_dir))

    added = client.post("/api/drafts", json={"anchor": "class:HintPolicy", "text": "Why?"})
    listed = client.get("/api/drafts").json()["drafts"]

    assert added.status_code == 201
    assert [(d["anchor"], d["text"], d["thread_id"]) for d in listed] == [
        ("class:HintPolicy", "Why?", None)
    ]


def test_a_draft_can_be_edited(plan_file: Path, static_dir: Path) -> None:
    client = TestClient(create_app(plan_file, static_dir))
    draft = client.post("/api/drafts", json={"anchor": "risk:1", "text": "Why?"}).json()

    client.put(f"/api/drafts/{draft['id']}", json={"text": "Why a class?"})

    assert [d["text"] for d in client.get("/api/drafts").json()["drafts"]] == ["Why a class?"]


def test_a_draft_can_be_discarded(plan_file: Path, static_dir: Path) -> None:
    client = TestClient(create_app(plan_file, static_dir))
    kept = client.post("/api/drafts", json={"anchor": "risk:1", "text": "Keep"}).json()
    gone = client.post("/api/drafts", json={"anchor": "risk:2", "text": "Hmm"}).json()

    discarded = client.delete(f"/api/drafts/{gone['id']}")

    assert discarded.status_code == 204
    assert [d["id"] for d in client.get("/api/drafts").json()["drafts"]] == [kept["id"]]


def test_a_reply_draft_takes_its_threads_anchor(plan_file: Path, static_dir: Path) -> None:
    thread = ThreadStore(plan_file.parent / "comments.json").create("risk:1", "Agree?")
    client = TestClient(create_app(plan_file, static_dir))

    draft = client.post("/api/drafts", json={"thread_id": thread.id, "text": "Yes"}).json()

    assert (draft["anchor"], draft["thread_id"]) == ("risk:1", thread.id)


def test_a_draft_without_anchor_or_thread_is_422(plan_file: Path, static_dir: Path) -> None:
    client = TestClient(create_app(plan_file, static_dir))

    response = client.post("/api/drafts", json={"text": "?"})

    assert response.status_code == 422
    assert response.json() == {"errors": ["a draft needs an anchor or a thread_id"]}


def test_a_reply_draft_to_an_unknown_thread_is_404(plan_file: Path, static_dir: Path) -> None:
    client = TestClient(create_app(plan_file, static_dir))

    response = client.post("/api/drafts", json={"thread_id": "t-nope", "text": "?"})

    assert response.status_code == 404
    assert client.get("/api/drafts").json() == {"drafts": []}


def test_blank_draft_is_422(plan_file: Path, static_dir: Path) -> None:
    client = TestClient(create_app(plan_file, static_dir))

    response = client.post("/api/drafts", json={"anchor": "risk:1", "text": "  "})

    assert response.status_code == 422
    assert response.json() == {"errors": ["comment text is empty"]}


def test_editing_an_unknown_draft_is_404(plan_file: Path, static_dir: Path) -> None:
    client = TestClient(create_app(plan_file, static_dir))

    response = client.put("/api/drafts/d-nope", json={"text": "x"})

    assert response.status_code == 404
    assert response.json() == {"errors": ["no draft 'd-nope'"]}


def test_drafts_are_not_announced_until_the_review_is_submitted(
    plan_file: Path, static_dir: Path
) -> None:
    store = ThreadStore(plan_file.parent / "comments.json")
    thread = store.create("risk:1", "Agree?")
    with (
        TestClient(create_app(plan_file, static_dir)) as client,
        client.websocket_connect("/events") as events,
    ):
        client.post("/api/drafts", json={"anchor": "class:HintPolicy", "text": "Why?"})
        client.post("/api/drafts", json={"thread_id": thread.id, "text": "Thanks"})
        submitted = client.post("/api/review").json()

        # The first event is the whole review: drafts were never announced on their own.
        event = events.receive_json()
    new_thread = submitted["comments"][0]["thread_id"]
    assert event == {
        "type": "review_submitted",
        "comments": [
            {
                "type": "comment",
                "thread_id": new_thread,
                "anchor": "class:HintPolicy",
                "text": "Why?",
            },
            {"type": "reply", "thread_id": thread.id, "anchor": "risk:1", "text": "Thanks"},
        ],
    }
    assert submitted == {"comments": event["comments"]}


def test_submitting_a_review_turns_drafts_into_threads_and_clears_them(
    plan_file: Path, static_dir: Path
) -> None:
    thread = ThreadStore(plan_file.parent / "comments.json").create("risk:1", "Agree?")
    client = TestClient(create_app(plan_file, static_dir))
    client.post("/api/drafts", json={"anchor": "class:HintPolicy", "text": "Why?"})
    client.post("/api/drafts", json={"thread_id": thread.id, "text": "Thanks"})

    client.post("/api/review")
    threads = client.get("/api/threads").json()["threads"]

    assert [(t["anchor"], [m["text"] for m in t["messages"]]) for t in threads] == [
        ("risk:1", ["Agree?", "Thanks"]),
        ("class:HintPolicy", ["Why?"]),
    ]
    assert client.get("/api/drafts").json() == {"drafts": []}


def test_a_review_with_a_reply_to_a_vanished_thread_submits_nothing(
    plan_file: Path, static_dir: Path
) -> None:
    comments = plan_file.parent / "comments.json"
    thread = ThreadStore(comments).create("risk:1", "Agree?")
    client = TestClient(create_app(plan_file, static_dir))
    client.post("/api/drafts", json={"anchor": "class:HintPolicy", "text": "Why?"})
    client.post("/api/drafts", json={"thread_id": thread.id, "text": "Thanks"})
    comments.write_text("[]")

    response = client.post("/api/review")

    assert response.status_code == 404
    assert client.get("/api/threads").json() == {"threads": []}
    assert len(client.get("/api/drafts").json()["drafts"]) == 2


def test_submitting_an_empty_review_is_422(plan_file: Path, static_dir: Path) -> None:
    client = TestClient(create_app(plan_file, static_dir))

    response = client.post("/api/review")

    assert response.status_code == 422
    assert response.json() == {"errors": ["no drafts to submit"]}


def test_claudes_replies_through_the_cli_are_not_announced(
    plan_file: Path, static_dir: Path
) -> None:
    store = ThreadStore(plan_file.parent / "comments.json")
    thread = store.create("risk:1", "Agree?")
    with (
        TestClient(create_app(plan_file, static_dir)) as client,
        client.websocket_connect("/events") as events,
    ):
        store.reply(thread.id, "Yes, see mitigation.", author="claude")  # as the CLI does
        client.post("/api/drafts", json={"anchor": "risk:2", "text": "Ok"})
        client.post("/api/review")

        assert events.receive_json()["type"] == "review_submitted"


def test_approve_is_refused_while_drafts_are_unsent(plan_file: Path, static_dir: Path) -> None:
    client = TestClient(create_app(plan_file, static_dir))
    client.post("/api/drafts", json={"anchor": "risk:1", "text": "Hmm"})

    response = client.post("/api/approve")

    assert response.status_code == 409
    assert response.json() == {"errors": ["1 unsent draft(s): submit or discard them first"]}
    assert not (plan_file.parent / "approved.json").exists()


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


def test_page_is_revalidated_so_an_upgraded_viewer_is_never_served_stale(
    plan_file: Path, static_dir: Path
) -> None:
    client = TestClient(create_app(plan_file, static_dir))

    assert client.get("/").headers["cache-control"] == "no-cache"


def test_pages_are_told_when_drafts_change_on_disk(plan_file: Path, static_dir: Path) -> None:
    app = create_app(plan_file, static_dir, poll_interval=0.01)

    with TestClient(app) as client, client.websocket_connect("/api/updates") as updates:
        DraftStore(plan_file.parent / "drafts.json").add("risk:1", "from another tab")

        assert updates.receive_json() == {"type": "drafts_changed"}


def test_pages_are_told_when_comment_threads_change_on_disk(
    plan_file: Path, static_dir: Path
) -> None:
    app = create_app(plan_file, static_dir, poll_interval=0.01)

    with TestClient(app) as client, client.websocket_connect("/api/updates") as updates:
        ThreadStore(plan_file.parent / "comments.json").create("risk:1", "via the CLI")

        assert updates.receive_json() == {"type": "threads_changed"}


def test_approval_state_can_be_read(plan_file: Path, static_dir: Path) -> None:
    client = TestClient(create_app(plan_file, static_dir))

    before = client.get("/api/approve").json()
    client.post("/api/approve")
    after = client.get("/api/approve").json()

    assert before == {"approved": False}
    assert after["approved"] is True
    assert after["plan_sha256"] == hashlib.sha256(plan_file.read_bytes()).hexdigest()


def test_status_is_none_until_claude_sets_one(plan_file: Path, static_dir: Path) -> None:
    client = TestClient(create_app(plan_file, static_dir))

    assert client.get("/api/status").json() == {"status": None}


def test_status_set_by_the_cli_can_be_read(plan_file: Path, static_dir: Path) -> None:
    StatusStore(plan_file.parent / "status.json").set("Answering questions")
    client = TestClient(create_app(plan_file, static_dir))

    status = client.get("/api/status").json()["status"]

    assert (status["text"], status["done"]) == ("Answering questions", False)


def test_pages_are_told_when_the_status_changes(plan_file: Path, static_dir: Path) -> None:
    app = create_app(plan_file, static_dir, poll_interval=0.01)

    with TestClient(app) as client, client.websocket_connect("/api/updates") as updates:
        StatusStore(plan_file.parent / "status.json").set("Architect revising")

        assert updates.receive_json() == {"type": "status_changed"}


def test_a_submitted_review_is_kept_as_the_last_event(plan_file: Path, static_dir: Path) -> None:
    with (
        TestClient(create_app(plan_file, static_dir)) as client,
        client.websocket_connect("/events") as events,
    ):
        client.post("/api/drafts", json={"anchor": "class:HintPolicy", "text": "Why?"})
        client.post("/api/review")
        sent = events.receive_json()

    kept = json.loads((plan_file.parent / "last_event.json").read_text())
    assert kept["event"] == sent
    assert kept["sent_at"]


def test_an_approval_is_kept_as_the_last_event(plan_file: Path, static_dir: Path) -> None:
    with TestClient(create_app(plan_file, static_dir)) as client:
        client.post("/api/drafts", json={"anchor": "class:HintPolicy", "text": "Why?"})
        client.post("/api/review")
        ThreadStore(plan_file.parent / "comments.json").set_resolved(
            ThreadStore(plan_file.parent / "comments.json").all()[0].id, True
        )
        client.post("/api/approve")

    kept = json.loads((plan_file.parent / "last_event.json").read_text())
    assert kept["event"] == {"type": "approved"}


def test_an_event_is_kept_even_with_no_monitor_connected(plan_file: Path, static_dir: Path) -> None:
    with TestClient(create_app(plan_file, static_dir)) as client:
        assert client.post("/api/approve").status_code == 200

    kept = json.loads((plan_file.parent / "last_event.json").read_text())
    assert kept["event"] == {"type": "approved"}


def test_pages_are_not_told_about_the_kept_event(plan_file: Path, static_dir: Path) -> None:
    app = create_app(plan_file, static_dir, poll_interval=0.01)

    with TestClient(app) as client, client.websocket_connect("/api/updates") as updates:
        client.post("/api/approve")  # keeps an event; approved.json is not watched either
        StatusStore(plan_file.parent / "status.json").set("Approved, implementing")

        assert updates.receive_json() == {"type": "status_changed"}


def test_last_event_is_null_until_something_is_sent(plan_file: Path, static_dir: Path) -> None:
    client = TestClient(create_app(plan_file, static_dir))

    assert client.get("/api/last-event").json() == {"last_event": None}


def test_last_event_says_whether_claude_answered(plan_file: Path, static_dir: Path) -> None:
    with TestClient(create_app(plan_file, static_dir)) as client:
        client.post("/api/approve")
        before = client.get("/api/last-event").json()["last_event"]
        StatusStore(plan_file.parent / "status.json").set("Approved, implementing")
        after = client.get("/api/last-event").json()["last_event"]

    assert before["type"] == "approved"
    assert before["sent_at"]
    assert before["answered"] is False
    assert after["answered"] is True


def test_resend_sends_the_kept_event_again_unchanged(plan_file: Path, static_dir: Path) -> None:
    with TestClient(create_app(plan_file, static_dir)) as client:
        client.post("/api/drafts", json={"anchor": "class:HintPolicy", "text": "Why?"})
        client.post("/api/review")  # sent while no Monitor was connected
        with client.websocket_connect("/events") as events:
            response = client.post("/api/resend")

            assert response.json() == {"sent": True}
            resent = events.receive_json()
    kept = json.loads((plan_file.parent / "last_event.json").read_text())
    assert resent["type"] == "review_submitted"
    assert resent["comments"][0]["text"] == "Why?"
    assert resent == kept["event"]


def test_resend_re_stamps_when_the_event_was_sent(plan_file: Path, static_dir: Path) -> None:
    kept_file = plan_file.parent / "last_event.json"
    kept_file.write_text(
        json.dumps({"event": {"type": "approved"}, "sent_at": "2020-01-01T00:00:00Z"})
    )
    client = TestClient(create_app(plan_file, static_dir))

    assert client.post("/api/resend").json() == {"sent": True}

    sent_at = client.get("/api/last-event").json()["last_event"]["sent_at"]
    assert not sent_at.startswith("2020")
    assert not json.loads(kept_file.read_text())["sent_at"].startswith("2020")


def test_resend_sends_nothing_once_claude_set_a_status(plan_file: Path, static_dir: Path) -> None:
    kept_file = plan_file.parent / "last_event.json"
    with (
        TestClient(create_app(plan_file, static_dir)) as client,
        client.websocket_connect("/events") as events,
    ):
        client.post("/api/approve")
        events.receive_json()
        StatusStore(plan_file.parent / "status.json").set("Approved, implementing")
        kept_before = kept_file.read_text()

        response = client.post("/api/resend")

        assert response.json()["sent"] is False
        assert response.json()["status"]["text"] == "Approved, implementing"
        assert kept_file.read_text() == kept_before
        # Sentinel: a socket only blocks on silence, so prove the next event is the next send.
        client.post("/api/drafts", json={"anchor": "class:HintPolicy", "text": "Why?"})
        client.post("/api/review")
        assert events.receive_json()["type"] == "review_submitted"


def test_resend_with_nothing_kept_is_409(plan_file: Path, static_dir: Path) -> None:
    client = TestClient(create_app(plan_file, static_dir))

    response = client.post("/api/resend")

    assert response.status_code == 409
    assert response.json() == {"errors": ["nothing has been sent to Claude yet"]}
    assert not (plan_file.parent / "last_event.json").exists()


def test_resend_works_after_a_server_restart(plan_file: Path, static_dir: Path) -> None:
    with TestClient(create_app(plan_file, static_dir)) as client:
        client.post("/api/approve")

    with (
        TestClient(create_app(plan_file, static_dir)) as restarted,
        restarted.websocket_connect("/events") as events,
    ):
        assert restarted.post("/api/resend").json() == {"sent": True}
        assert events.receive_json() == {"type": "approved"}


def test_an_event_still_reaches_claude_when_last_event_json_is_broken(
    plan_file: Path, static_dir: Path
) -> None:
    kept = plan_file.parent / "last_event.json"
    kept.write_bytes(b"{bad")

    with (
        TestClient(create_app(plan_file, static_dir)) as client,
        client.websocket_connect("/events") as events,
    ):
        assert client.post("/api/approve").status_code == 200

        assert events.receive_json() == {"type": "approved"}
    assert kept.read_bytes() == b"{bad"


BAD_JSON = "Invalid JSON: key must be a string at line 1 column 2"


def _named(path: Path, line: str = BAD_JSON) -> dict[str, list[str]]:
    return {"errors": [f"{path.as_posix()}: {line}"]}


def test_a_broken_comments_json_is_422_naming_it_while_the_plan_still_loads(
    plan_file: Path, static_dir: Path
) -> None:
    comments = plan_file.parent / "comments.json"
    comments.write_bytes(b"{bad")
    client = TestClient(create_app(plan_file, static_dir))

    for response in (client.get("/api/threads"), client.post("/api/threads/t-1/resolve")):
        assert response.status_code == 422
        assert response.json() == _named(comments)
    assert client.get("/api/plan").status_code == 200
    assert comments.read_bytes() == b"{bad"


def test_drafts_review_and_approve_refuse_with_the_broken_files_name(
    plan_file: Path, static_dir: Path
) -> None:
    drafts = plan_file.parent / "drafts.json"
    drafts.write_bytes(b"{bad")
    client = TestClient(create_app(plan_file, static_dir))

    responses = [
        client.get("/api/drafts"),
        client.post("/api/drafts", json={"anchor": "tab:plan", "text": "hi"}),
        client.post("/api/review"),
        client.post("/api/approve"),
    ]

    for response in responses:
        assert response.status_code == 422
        assert response.json() == _named(drafts)
    assert not (plan_file.parent / "approved.json").exists()
    assert drafts.read_bytes() == b"{bad"


def test_a_broken_status_or_last_event_json_is_422_naming_it(
    plan_file: Path, static_dir: Path
) -> None:
    status = plan_file.parent / "status.json"
    last_event = plan_file.parent / "last_event.json"
    client = TestClient(create_app(plan_file, static_dir))
    client.post("/api/approve")  # keeps a valid last_event.json
    status.write_bytes(b"{bad")

    for response in (
        client.get("/api/status"),
        client.get("/api/last-event"),
        client.post("/api/resend"),
    ):
        assert response.status_code == 422
        assert response.json() == _named(status)

    status.unlink()
    StatusStore(status).set("working")
    last_event.write_bytes(b"{bad")

    for response in (client.get("/api/last-event"), client.post("/api/resend")):
        assert response.status_code == 422
        assert response.json() == _named(last_event)


@pytest.mark.parametrize(
    ("content", "line"),
    [
        (b"{bad", BAD_JSON),
        (b"[]", "Input should be an object"),
    ],
)
def test_a_broken_approved_json_is_422_and_approving_leaves_it(
    plan_file: Path, static_dir: Path, content: bytes, line: str
) -> None:
    approved = plan_file.parent / "approved.json"
    approved.write_bytes(content)
    client = TestClient(create_app(plan_file, static_dir))

    for response in (client.get("/api/approve"), client.post("/api/approve")):
        assert response.status_code == 422
        assert response.json() == _named(approved, line)
    assert approved.read_bytes() == content


def test_an_approved_json_with_extra_fields_still_reads_and_answers_only_the_known_ones(
    plan_file: Path, static_dir: Path
) -> None:
    approved = plan_file.parent / "approved.json"
    approved.write_text(
        json.dumps({"approved_at": "2026-01-01T00:00:00+00:00", "plan_sha256": "abc", "by": "me"})
    )
    client = TestClient(create_app(plan_file, static_dir))

    response = client.get("/api/approve")

    assert response.status_code == 200
    assert response.json() == {
        "approved": True,
        "approved_at": "2026-01-01T00:00:00+00:00",
        "plan_sha256": "abc",
    }


def test_serve_still_opens_an_old_plan(plan_file: Path, static_dir: Path) -> None:
    shutil.copy(Path(__file__).parent / "fixtures" / "plan-0.1.11.json", plan_file)
    client = TestClient(create_app(plan_file, static_dir))

    response = client.get("/api/plan")

    assert response.status_code == 200
    assert response.json()["classes"][0]["id"] == "class:HintPolicy"
