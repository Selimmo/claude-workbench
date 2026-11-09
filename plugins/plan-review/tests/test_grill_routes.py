"""The grill page's HTTP routes, their events, and the page routes."""

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from plan_review.event_log import EventLog
from plan_review.events import AgentEvents
from plan_review.grill import GrillStore, SubmittedAnswer
from plan_review.grill_drafts import AnswerDraft, GrillDraftStore
from plan_review.grill_routes import grill_routes
from plan_review.grill_turn import Turn
from plan_review.last_event import LastEventStore
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
    folder = tmp_path / ".plan-review" / "work" / "42"
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


def test_api_grill_returns_the_state_with_the_reply_limit(
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
    assert body["max_replies"] == 3
    assert "max_asks" not in body


def test_answer_drafts_can_be_saved_replaced_and_discarded(
    work: Path, static_dir: Path, store: GrillStore
) -> None:
    post(store, title="T", round=[question("q1"), question("q2")])
    with TestClient(create_app(work / "plan.json", static_dir)) as client:
        assert client.get("/api/grill/drafts").json() == {"drafts": {}}

        saved = client.put("/api/grill/drafts/q1", json={"kind": "choice", "choice_id": "a"})
        client.put("/api/grill/drafts/q1", json={"kind": "other", "text": "Mine"})
        client.put("/api/grill/drafts/q2", json={"kind": "choice", "choice_id": "b"})

        assert saved.status_code == 200
        drafts = client.get("/api/grill/drafts").json()["drafts"]
        assert drafts["q1"]["kind"] == "other"
        assert drafts["q2"]["choice_id"] == "b"

        assert client.delete("/api/grill/drafts/q2").status_code == 204
        assert list(client.get("/api/grill/drafts").json()["drafts"]) == ["q1"]

        # drafts are the owner's alone: nothing went to Claude
        assert not (work / "last_event.json").exists()

        assert (
            client.put("/api/grill/drafts/nope", json={"kind": "other", "text": "x"}).status_code
            == 404
        )
        assert client.put("/api/grill/drafts/q1", json={"kind": "other"}).status_code == 200
        assert client.put("/api/grill/drafts/q1", json={"kind": "choice"}).status_code == 422


def test_an_other_draft_is_accepted_after_three_replies_and_own_or_ask_are_422(
    work: Path, static_dir: Path, store: GrillStore
) -> None:
    post(store, title="T", round=[question("q1"), question("q2")])
    for i in range(3):
        answers = [SubmittedAnswer(question_id="q1", kind="other", text=f"other {i}")]
        if i == 0:
            answers.append(SubmittedAnswer(question_id="q2", kind="choice", choice_id="a"))
        store.submit(answers)
        post(store, replies=[{"question_id": "q1", "text": "Because."}])
    client = TestClient(create_app(work / "plan.json", static_dir))

    answered = client.put("/api/grill/drafts/q2", json={"kind": "other", "text": "again"})
    other = client.put("/api/grill/drafts/q1", json={"kind": "other", "text": "final"})
    own = client.put("/api/grill/drafts/q1", json={"kind": "own", "text": "Mine"})
    ask = client.put("/api/grill/drafts/q1", json={"kind": "ask", "text": "Why?"})

    assert answered.status_code == 404
    assert other.status_code == 200
    assert (own.status_code, ask.status_code) == (422, 422)


def test_submitting_an_other_draft_tells_claude_its_text(
    work: Path, static_dir: Path, store: GrillStore
) -> None:
    post(store, title="T", round=[question("q1"), question("q2")])
    with (
        TestClient(create_app(work / "plan.json", static_dir)) as client,
        client.websocket_connect("/events") as events,
    ):
        client.put("/api/grill/drafts/q1", json={"kind": "choice", "choice_id": "b", "text": "ok"})
        client.put("/api/grill/drafts/q2", json={"kind": "other", "text": "Why?"})

        response = client.post("/api/grill/submit")

        sent = events.receive_json()
    expected = [
        {"question_id": "q1", "kind": "choice", "choice_id": "b", "text": "ok"},
        {"question_id": "q2", "kind": "other", "text": "Why?"},
    ]
    assert response.status_code == 200
    assert sent == {"type": "grill_submitted", "answers": expected}
    assert json.loads((work / "last_event.json").read_text())["event"] == sent
    state = store.get()
    assert state.rounds[0].questions[0].answer is not None
    assert state.rounds[0].questions[1].answer is None
    assert state.rounds[0].questions[1].thread[0].text == "Why?"
    assert json.loads((work / "grill_drafts.json").read_text()) == {}


def test_a_broken_log_refuses_the_grill_submit_before_anything_is_written(
    work: Path, static_dir: Path, store: GrillStore
) -> None:
    post(store, title="T", round=[question("q1")])
    (work / "events.json").write_text("{ nope")
    client = TestClient(create_app(work / "plan.json", static_dir))
    client.put("/api/grill/drafts/q1", json={"kind": "choice", "choice_id": "a"})

    refused = client.post("/api/grill/submit")

    assert refused.status_code == 422
    assert "events.json" in refused.json()["errors"][0]
    assert store.get().rounds[0].questions[0].answer is None
    assert list(client.get("/api/grill/drafts").json()["drafts"]) == ["q1"]

    (work / "events.json").unlink()  # the owner repairs it and submits again

    assert client.post("/api/grill/submit").status_code == 200
    assert store.get().rounds[0].questions[0].answer is not None
    assert client.get("/api/grill/drafts").json()["drafts"] == {}


def test_a_broken_log_refuses_the_confirm_before_anything_is_written(
    work: Path, static_dir: Path, store: GrillStore
) -> None:
    post(store, title="T", done=True)
    (work / "events.json").write_text("{ nope")
    client = TestClient(create_app(work / "plan.json", static_dir))

    refused = client.post("/api/grill/confirm")

    assert refused.status_code == 422
    assert "events.json" in refused.json()["errors"][0]
    assert store.get().confirmed_at is None

    (work / "events.json").unlink()  # the owner repairs it and tries again

    assert client.post("/api/grill/confirm").status_code == 200


def test_a_broken_log_refuses_the_reopen_before_anything_is_written(
    work: Path, static_dir: Path, store: GrillStore
) -> None:
    post(store, title="T", done=True)
    (work / "events.json").write_text("{ nope")
    client = TestClient(create_app(work / "plan.json", static_dir))

    refused = client.post("/api/grill/reopen", json={"text": "Ask about X"})

    assert refused.status_code == 422
    assert "events.json" in refused.json()["errors"][0]
    assert store.get().done

    (work / "events.json").unlink()  # the owner repairs it and tries again

    assert client.post("/api/grill/reopen", json={"text": "Ask about X"}).status_code == 200


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
    assert (
        client.put("/api/grill/drafts/q1", json={"kind": "other", "text": "x"}).status_code == 404
    )
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
        reply = client.put("/api/grill/drafts/q1", json={"kind": "other", "text": "late"})
        status.append(reply.status_code)

    drafts = GrillDraftStore(work / "grill_drafts.json")
    with drafts.held():  # a submit in progress
        thread = threading.Thread(target=late_put)
        thread.start()
        time.sleep(0.3)  # the PUT is now waiting for the lock
        store.submit([SubmittedAnswer(question_id="q1", kind="choice", choice_id="a")])
    thread.join()

    assert status == [404]
    assert drafts.all() == {}


def test_the_server_names_run_files_by_their_project_relative_path_as_serve_does(
    tmp_path: Path, static_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)  # `plan-review serve` runs from the project root
    work = Path(".plan-review/work/42")
    (tmp_path / work).mkdir(parents=True)
    issue = {"id": "42", "kind": "issue", "title": "x"}
    (tmp_path / work / "plan.json").write_text(json.dumps({"issue": issue}))
    for name in ("grill.json", "comments.json"):
        (tmp_path / work / name).write_text("{bad")
    client = TestClient(create_app(work / "plan.json", static_dir))
    bad_json = "Invalid JSON: key must be a string at line 1 column 2"

    expected = {
        "/api/grill": f".plan-review/work/42/grill.json: {bad_json}",
        "/api/plan": ".plan-review/work/42/plan.json: summary: Field required",
        "/api/threads": f".plan-review/work/42/comments.json: {bad_json}",
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


def test_a_draft_left_on_a_question_claude_closed_does_not_block_the_submit(
    work: Path, static_dir: Path, store: GrillStore
) -> None:
    post(store, title="T", round=[question("q1"), question("q2")])
    store.submit(
        [
            SubmittedAnswer(question_id="q1", kind="other", text="Mine"),
            SubmittedAnswer(question_id="q2", kind="choice", choice_id="a"),
        ]
    )
    with TestClient(create_app(work / "plan.json", static_dir)) as client:
        # q1 waits for Claude; the owner changes their mind meanwhile and a draft is saved
        client.put("/api/grill/drafts/q1", json={"kind": "choice", "choice_id": "b", "text": "x"})
        # Claude settles q1 and asks q3 (posted by the CLI, so the server is not told)
        post(
            store,
            decisions=[
                {
                    "id": "d1",
                    "topic": "T",
                    "decision": "Mine",
                    "choice": "Mine",
                    "question_id": "q1",
                }
            ],
            round=[question("q3")],
        )
        client.put("/api/grill/drafts/q3", json={"kind": "choice", "choice_id": "a"})

        reply = client.post("/api/grill/submit")

        assert reply.status_code == 200, reply.text
        assert [a["question_id"] for a in reply.json()["answers"]] == ["q3"]
        assert client.get("/api/grill/drafts").json() == {"drafts": {}}


def test_grill_answers_a_reopen_and_a_confirm_reach_the_log(
    work: Path, static_dir: Path, store: GrillStore
) -> None:
    post(store, title="T", round=[question("q1")])
    log = EventLog(work / "events.json")
    with TestClient(create_app(work / "plan.json", static_dir)) as client:
        client.put("/api/grill/drafts/q1", json={"kind": "choice", "choice_id": "a"})
        client.post("/api/grill/submit")
        post(store, done=True)
        client.post("/api/grill/reopen", json={"text": "more"})
        post(store, done=True)
        client.post("/api/grill/confirm")

    seen: list[object] = []
    while (event := log.offer()) is not None:
        seen.append(event["type"])
        log.confirm()
    assert seen == ["grill_submitted", "grill_reopened", "grill_confirmed"]


class ClearingFails(GrillDraftStore):
    def clear(self, question_ids: set[str]) -> None:
        raise OSError("disk full")


def test_a_grill_submit_is_recorded_before_its_drafts_are_cleared(
    work: Path, store: GrillStore
) -> None:
    post(store, title="T", round=[question("q1")])
    drafts = ClearingFails(work / "grill_drafts.json")
    drafts.put("q1", AnswerDraft(kind="choice", choice_id="a"))
    app = FastAPI()
    events = AgentEvents(LastEventStore(work / "last_event.json"), EventLog(work / "events.json"))
    app.include_router(grill_routes(store, drafts, events, label="#42"))

    with pytest.raises(OSError, match="disk full"):
        TestClient(app).post("/api/grill/submit")

    event = EventLog(work / "events.json").offer()
    assert event is not None
    assert event["type"] == "grill_submitted"
