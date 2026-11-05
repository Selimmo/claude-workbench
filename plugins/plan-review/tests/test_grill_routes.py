"""The grill page's HTTP routes, their events, and the page routes."""

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from plan_review.grill import GrillStore, SubmittedAnswer
from plan_review.grill_turn import Turn
from plan_review.server import create_app


def question(qid: str) -> dict[str, Any]:
    return {
        "id": qid,
        "title": f"Question {qid}?",
        "explanation": "Because.",
        "choices": [
            {"id": "a", "label": "Choice a", "description": "About a"},
            {"id": "b", "label": "Choice b", "description": "About b"},
        ],
    }


@pytest.fixture
def work(tmp_path: Path) -> Path:
    folder = tmp_path / ".claude" / "work" / "42"
    folder.mkdir(parents=True)
    return folder


@pytest.fixture
def static_dir(tmp_path: Path) -> Path:
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<h1>plan-review</h1>")
    return static


@pytest.fixture
def store(work: Path) -> GrillStore:
    return GrillStore(work / "grill.json")


def post(store: GrillStore, **fields: Any) -> None:
    store.post(Turn.model_validate(fields))


def test_api_grill_returns_the_state_with_the_ask_limit(
    work: Path, static_dir: Path, store: GrillStore
) -> None:
    client = TestClient(create_app(work / "plan.json", static_dir))

    missing = client.get("/api/grill")
    assert missing.status_code == 404
    assert missing.json() == {"errors": [f"{(work / 'grill.json').as_posix()}: file not found"]}

    post(store, title="Add hints", round=[question("q1")])
    body = client.get("/api/grill").json()

    assert body["title"] == "Add hints"
    assert body["label"] == "#42"  # the run folder's name, as the CLI labels it
    assert body["rounds"][0]["questions"][0]["id"] == "q1"
    assert body["rounds"][0]["questions"][0]["choices"][0]["description"] == "About a"
    assert body["max_asks"] == 3


def test_answer_drafts_can_be_saved_replaced_and_discarded(
    work: Path, static_dir: Path, store: GrillStore
) -> None:
    post(store, title="T", round=[question("q1"), question("q2")])
    with TestClient(create_app(work / "plan.json", static_dir)) as client:
        assert client.get("/api/grill/drafts").json() == {"drafts": {}}

        saved = client.put("/api/grill/drafts/q1", json={"kind": "choice", "choice_id": "a"})
        client.put("/api/grill/drafts/q1", json={"kind": "own", "text": "Mine"})
        client.put("/api/grill/drafts/q2", json={"kind": "choice", "choice_id": "b"})

        assert saved.status_code == 200
        drafts = client.get("/api/grill/drafts").json()["drafts"]
        assert drafts["q1"]["kind"] == "own"
        assert drafts["q2"]["choice_id"] == "b"

        assert client.delete("/api/grill/drafts/q2").status_code == 204
        assert list(client.get("/api/grill/drafts").json()["drafts"]) == ["q1"]

        # drafts are the owner's alone: nothing went to Claude
        assert not (work / "last_event.json").exists()

        assert (
            client.put("/api/grill/drafts/nope", json={"kind": "own", "text": "x"}).status_code
            == 404
        )
        assert (
            client.put("/api/grill/drafts/q1", json={"kind": "own", "text": " "}).status_code == 422
        )
        assert client.put("/api/grill/drafts/q1", json={"kind": "choice"}).status_code == 422


def test_an_answered_question_has_no_drafts_and_a_fourth_ask_is_refused(
    work: Path, static_dir: Path, store: GrillStore
) -> None:
    post(store, title="T", round=[question("q1"), question("q2")])
    for i in range(3):
        answers = [SubmittedAnswer(question_id="q1", kind="ask", text=f"ask {i}")]
        if i == 0:
            answers.append(SubmittedAnswer(question_id="q2", kind="own", text="Z"))
        store.submit(answers)
        post(store, replies=[{"question_id": "q1", "text": "Because."}])
    client = TestClient(create_app(work / "plan.json", static_dir))

    answered = client.put("/api/grill/drafts/q2", json={"kind": "own", "text": "again"})
    fourth = client.put("/api/grill/drafts/q1", json={"kind": "ask", "text": "once more"})
    still_fine = client.put("/api/grill/drafts/q1", json={"kind": "choice", "choice_id": "a"})

    assert answered.status_code == 404
    assert fourth.status_code == 422
    assert "3 asks back" in fourth.json()["errors"][0]
    assert still_fine.status_code == 200


def test_submitting_turns_drafts_into_answers_and_tells_claude_once(
    work: Path, static_dir: Path, store: GrillStore
) -> None:
    post(store, title="T", round=[question("q1"), question("q2")])
    with (
        TestClient(create_app(work / "plan.json", static_dir)) as client,
        client.websocket_connect("/events") as events,
    ):
        client.put("/api/grill/drafts/q1", json={"kind": "choice", "choice_id": "b", "text": "ok"})
        client.put("/api/grill/drafts/q2", json={"kind": "ask", "text": "Why?"})

        response = client.post("/api/grill/submit")

        sent = events.receive_json()
    expected = [
        {"question_id": "q1", "kind": "choice", "choice_id": "b", "text": "ok"},
        {"question_id": "q2", "kind": "ask", "text": "Why?"},
    ]
    assert response.status_code == 200
    assert sent == {"type": "grill_submitted", "answers": expected}
    assert json.loads((work / "last_event.json").read_text())["event"] == sent
    state = store.get()
    assert state.rounds[0].questions[0].answer is not None
    assert state.rounds[0].questions[1].thread[0].text == "Why?"
    assert json.loads((work / "grill_drafts.json").read_text()) == {}


def test_an_incomplete_or_untimely_submit_is_refused(
    work: Path, static_dir: Path, store: GrillStore
) -> None:
    post(store, title="T", round=[question("q1"), question("q2")])
    client = TestClient(create_app(work / "plan.json", static_dir))
    client.put("/api/grill/drafts/q1", json={"kind": "choice", "choice_id": "a"})

    incomplete = client.post("/api/grill/submit")

    assert incomplete.status_code == 422
    assert incomplete.json() == {"errors": ["q2: needs a response"]}
    assert list(client.get("/api/grill/drafts").json()["drafts"]) == ["q1"]  # kept
    assert store.get().open_questions()[0].id == "q1"

    client.put("/api/grill/drafts/q2", json={"kind": "choice", "choice_id": "a"})
    assert client.post("/api/grill/submit").status_code == 200

    # now it is Claude's turn: the answered question takes no more drafts, and a submit waits
    assert client.put("/api/grill/drafts/q1", json={"kind": "own", "text": "x"}).status_code == 404
    assert client.post("/api/grill/submit").status_code == 409


def test_confirm_and_reopen_send_their_events(
    work: Path, static_dir: Path, store: GrillStore
) -> None:
    post(store, title="T", round=[question("q1")])
    with (
        TestClient(create_app(work / "plan.json", static_dir)) as client,
        client.websocket_connect("/events") as events,
    ):
        assert client.post("/api/grill/confirm").status_code == 409  # not done yet
        assert client.post("/api/grill/reopen", json={"text": "more"}).status_code == 409

        store.submit([SubmittedAnswer(question_id="q1", kind="choice", choice_id="a")])
        post(store, done=True)

        assert client.post("/api/grill/reopen", json={"text": "  "}).status_code == 422
        assert client.post("/api/grill/reopen", json={"text": "Ask about X"}).status_code == 200
        assert events.receive_json() == {"type": "grill_reopened", "text": "Ask about X"}

        post(store, done=True)
        assert client.post("/api/grill/confirm").status_code == 200
        assert events.receive_json() == {"type": "grill_confirmed"}

        # once confirmed, the owner can do nothing more
        assert client.post("/api/grill/confirm").status_code == 409
        assert client.post("/api/grill/reopen", json={"text": "more"}).status_code == 409
        assert client.post("/api/grill/submit").status_code == 409

        # Claude's Monitor may have been away: Resend repeats the kept event
        assert client.post("/api/resend").json() == {"sent": True}
        assert events.receive_json() == {"type": "grill_confirmed"}
    assert store.get().confirmed_at is not None


def test_pages_are_told_when_the_grill_or_its_drafts_change(
    work: Path, static_dir: Path, store: GrillStore
) -> None:
    app = create_app(work / "plan.json", static_dir, poll_interval=0.01)

    with TestClient(app) as client, client.websocket_connect("/api/updates") as updates:
        post(store, title="T", round=[question("q1")])
        assert updates.receive_json() == {"type": "grill_changed"}

        client.put("/api/grill/drafts/q1", json={"kind": "choice", "choice_id": "a"})
        assert updates.receive_json() == {"type": "grill_drafts_changed"}


def test_grill_is_served_and_root_redirects_there_without_a_plan(
    work: Path, static_dir: Path
) -> None:
    client = TestClient(create_app(work / "plan.json", static_dir), follow_redirects=False)

    assert client.get("/grill").text == "<h1>plan-review</h1>"
    redirect = client.get("/")
    assert (redirect.status_code, redirect.headers["location"]) == (307, "/grill")

    (work / "plan.json").write_text("{not a valid plan")  # present, valid or not
    assert client.get("/").text == "<h1>plan-review</h1>"


def test_a_draft_cannot_land_on_a_question_a_submit_has_just_answered(
    work: Path, static_dir: Path, store: GrillStore
) -> None:
    import threading
    import time

    from plan_review.grill_drafts import GrillDraftStore

    post(store, title="T", round=[question("q1")])
    client = TestClient(create_app(work / "plan.json", static_dir))
    status: list[int] = []

    def late_put() -> None:
        reply = client.put("/api/grill/drafts/q1", json={"kind": "own", "text": "late"})
        status.append(reply.status_code)

    drafts = GrillDraftStore(work / "grill_drafts.json")
    with drafts.held():  # a submit in progress
        thread = threading.Thread(target=late_put)
        thread.start()
        time.sleep(0.3)  # the PUT is now waiting for the lock
        store.submit([SubmittedAnswer(question_id="q1", kind="own", text="Mine")])
    thread.join()

    assert status == [404]
    assert drafts.all() == {}


def test_the_server_names_run_files_by_their_project_relative_path_as_serve_does(
    tmp_path: Path, static_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)  # `plan-review serve` runs from the project root
    work = Path(".claude/work/42")
    (tmp_path / work).mkdir(parents=True)
    issue = {"id": "42", "kind": "issue", "title": "x"}
    (tmp_path / work / "plan.json").write_text(json.dumps({"issue": issue}))
    for name in ("grill.json", "comments.json"):
        (tmp_path / work / name).write_text("{bad")
    client = TestClient(create_app(work / "plan.json", static_dir))
    bad_json = "Invalid JSON: key must be a string at line 1 column 2"

    expected = {
        "/api/grill": f".claude/work/42/grill.json: {bad_json}",
        "/api/plan": ".claude/work/42/plan.json: summary: Field required",
        "/api/threads": f".claude/work/42/comments.json: {bad_json}",
    }
    for url, line in expected.items():
        response = client.get(url)
        assert response.status_code == 422
        assert response.json() == {"errors": [line]}


def test_a_broken_grill_drafts_json_is_422_while_the_grill_still_loads(
    work: Path, static_dir: Path, store: GrillStore
) -> None:
    post(store, title="Add hints", round=[question("q1")])
    drafts = work / "grill_drafts.json"
    drafts.write_bytes(b"{bad")
    client = TestClient(create_app(work / "plan.json", static_dir))
    named = {
        "errors": [f"{drafts.as_posix()}: Invalid JSON: key must be a string at line 1 column 2"]
    }

    assert client.get("/api/grill").status_code == 200
    responses = [
        client.get("/api/grill/drafts"),
        client.put("/api/grill/drafts/q1", json={"kind": "choice", "choice_id": "a"}),
        client.delete("/api/grill/drafts/q1"),
        client.post("/api/grill/submit"),
    ]

    for response in responses:
        assert response.status_code == 422
        assert response.json() == named
    assert drafts.read_bytes() == b"{bad"
    assert not (work / "last_event.json").exists()  # nothing was sent to Claude
