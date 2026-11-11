import shutil
import threading
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from plan_review.events.agent_events import AgentEvents
from plan_review.events.event_log import EventLog
from plan_review.events.last_event import LastEventStore
from plan_review.review.approval import approval_routes
from plan_review.review.approval_file import ApprovalFile, ApprovalRecord
from plan_review.review.drafts import DraftNotFound, DraftStore
from plan_review.review.service import review_routes
from plan_review.review.threads import Thread, ThreadStore
from plan_review.viewer.app import create_app


class OtherTabWritesDuringSubmit(ThreadStore):
    """Another viewer tab adds a draft while this tab's review is being written."""

    def __init__(self, path: Path, drafts: DraftStore) -> None:
        super().__init__(path)
        self._drafts = drafts

    def create(self, anchor: str, text: str) -> Thread:
        thread = super().create(anchor, text)
        if not any(d.text == "late" for d in self._drafts.all()):
            self._drafts.add("risk:2", "late")
        return thread


def test_a_draft_added_while_a_review_is_submitted_stays_for_the_next_review(
    tmp_path: Path,
) -> None:
    drafts = DraftStore(tmp_path / "drafts.json")
    threads = OtherTabWritesDuringSubmit(tmp_path / "comments.json", drafts)
    app = FastAPI()
    app.include_router(
        review_routes(
            threads,
            drafts,
            AgentEvents(
                LastEventStore(tmp_path / "last_event.json"), EventLog(tmp_path / "events.json")
            ),
            ApprovalFile(tmp_path / "approved.json"),
        )
    )
    drafts.add("risk:1", "early")

    TestClient(app).post("/api/review")

    assert [d.text for d in drafts.all()] == ["late"]


class OtherTabEditsDuringSubmit(ThreadStore):
    """Another tab edits the draft being submitted, while the review is being written."""

    def __init__(self, path: Path, drafts_file: Path, draft_id: str) -> None:
        super().__init__(path)
        self.edit_outcome = "not tried"
        self.editor: threading.Thread | None = None
        self._drafts_file = drafts_file
        self._draft_id = draft_id

    def _edit(self) -> None:
        try:
            DraftStore(self._drafts_file).edit(self._draft_id, "edited")  # its own request
            self.edit_outcome = "saved"
        except DraftNotFound:
            self.edit_outcome = "draft already sent"

    def create(self, anchor: str, text: str) -> Thread:
        if self.editor is None:
            self.editor = threading.Thread(target=self._edit)
            self.editor.start()
            self.editor.join(timeout=0.3)  # unlocked, the edit lands within this wait
        return super().create(anchor, text)


def test_an_edit_during_a_submit_is_not_silently_lost(tmp_path: Path) -> None:
    drafts = DraftStore(tmp_path / "drafts.json")
    draft = drafts.add("risk:1", "original")
    threads = OtherTabEditsDuringSubmit(
        tmp_path / "comments.json", tmp_path / "drafts.json", draft.id
    )
    app = FastAPI()
    app.include_router(
        review_routes(
            threads,
            drafts,
            AgentEvents(
                LastEventStore(tmp_path / "last_event.json"), EventLog(tmp_path / "events.json")
            ),
            ApprovalFile(tmp_path / "approved.json"),
        )
    )

    TestClient(app).post("/api/review")
    assert threads.editor is not None
    threads.editor.join()

    # Either the edit went into the review, or the owner is told the draft was sent.
    (sent,) = threads.all()
    assert (sent.messages[0].text, threads.edit_outcome) in [
        ("edited", "saved"),
        ("original", "draft already sent"),
    ]


def review_app(
    tmp_path: Path, threads: ThreadStore, drafts: DraftStore, approved: Path | None = None
) -> TestClient:
    app = FastAPI()
    events = AgentEvents(
        LastEventStore(tmp_path / "last_event.json"), EventLog(tmp_path / "events.json")
    )
    app.include_router(
        review_routes(threads, drafts, events, ApprovalFile(approved or tmp_path / "approved.json"))
    )
    return TestClient(app)


class ReadsLogWhileWriting(ThreadStore):
    """Another process (`plan-review wait`) looks at the log during the second thread's write."""

    def __init__(self, path: Path, log: EventLog) -> None:
        super().__init__(path)
        self._log = log
        self.seen_midway: object = "not looked"
        self._created = 0

    def create(self, anchor: str, text: str) -> Thread:
        self._created += 1
        if self._created == 2:
            seen = self._log.offer()
            self.seen_midway = "nothing yet" if seen is None else seen
        return super().create(anchor, text)


def test_a_review_is_not_visible_until_every_thread_is_written(tmp_path: Path) -> None:
    log = EventLog(tmp_path / "events.json")
    drafts = DraftStore(tmp_path / "drafts.json")
    threads = ReadsLogWhileWriting(tmp_path / "comments.json", log)
    drafts.add("risk:1", "one")
    drafts.add("risk:2", "two")

    review_app(tmp_path, threads, drafts).post("/api/review")

    assert threads.seen_midway == "nothing yet"
    event = log.offer()
    assert event is not None
    written = {t.id for t in threads.all()}
    comments: list[dict[str, str]] = event["comments"]
    assert {c["thread_id"] for c in comments} == written


class ClearingFails(DraftStore):
    def discard_all(self, draft_ids: set[str]) -> None:
        raise OSError("disk full")


def test_a_review_is_recorded_before_its_drafts_are_cleared(tmp_path: Path) -> None:
    drafts = ClearingFails(tmp_path / "drafts.json")
    drafts.add("risk:1", "one")
    client = review_app(tmp_path, ThreadStore(tmp_path / "comments.json"), drafts)

    with pytest.raises(OSError, match="disk full"):
        client.post("/api/review")

    event = EventLog(tmp_path / "events.json").offer()
    assert event is not None
    assert event["type"] == "review_submitted"


def test_a_broken_log_refuses_the_review_before_anything_is_written(tmp_path: Path) -> None:
    (tmp_path / "static").mkdir()
    (tmp_path / "events.json").write_text("{ nope")
    drafts = DraftStore(tmp_path / "drafts.json")
    threads = ThreadStore(tmp_path / "comments.json")
    drafts.add("risk:1", "first comment")
    client = TestClient(create_app(tmp_path / "plan.json", tmp_path / "static"))

    refused = client.post("/api/review")

    assert refused.status_code == 422
    assert "events.json" in refused.json()["errors"][0]
    assert threads.all() == []  # or a second submit would post every comment twice
    assert [d.text for d in drafts.all()] == ["first comment"]

    (tmp_path / "events.json").unlink()  # the owner repairs it and submits again

    assert client.post("/api/review").status_code == 200
    assert [t.anchor for t in threads.all()] == ["risk:1"]
    assert drafts.all() == []


def test_a_log_that_cannot_be_written_refuses_the_review_too(tmp_path: Path) -> None:
    (tmp_path / "static").mkdir()
    (tmp_path / "events.json").mkdir()
    drafts = DraftStore(tmp_path / "drafts.json")
    drafts.add("risk:1", "first comment")
    client = TestClient(create_app(tmp_path / "plan.json", tmp_path / "static"))

    refused = client.post("/api/review")

    assert refused.status_code == 422
    assert "events.json" in refused.json()["errors"][0]
    assert ThreadStore(tmp_path / "comments.json").all() == []
    assert [d.text for d in drafts.all()] == ["first comment"]


def test_review_routes_refuse_a_review_when_the_approval_file_holds_a_record(
    tmp_path: Path,
) -> None:
    threads = ThreadStore(tmp_path / "comments.json")
    drafts = DraftStore(tmp_path / "drafts.json")
    drafts.add("risk:1", "Agree?")
    elsewhere = tmp_path / "approval-record.json"
    ApprovalFile(elsewhere).write(
        ApprovalRecord(approved_at="2026-01-01T00:00:00+00:00", plan_sha256="abc")
    )

    response = review_app(tmp_path, threads, drafts, elsewhere).post("/api/review")

    assert response.status_code == 409
    assert response.json() == {"errors": ["the plan is approved: a review can't be sent any more"]}
    assert threads.all() == []
    assert EventLog(tmp_path / "events.json").offer() is None


class ReviewArrivesDuringApprove(ApprovalFile):
    """Another tab sends a review in the gap between approve's checks and its write."""

    def __init__(self, path: Path, work: Path) -> None:
        super().__init__(path)
        self._work = work
        self.review: dict[str, object] = {}
        self.sender: threading.Thread | None = None

    def _send(self) -> None:
        drafts = DraftStore(self._work / "drafts.json")  # its own request, on the same files
        drafts.add("risk:1", "late")
        reply = review_app(self._work, ThreadStore(self._work / "comments.json"), drafts).post(
            "/api/review"
        )
        self.review = {"status": reply.status_code, "body": reply.json()}

    def write(self, record: ApprovalRecord) -> None:
        if self.sender is None:
            self.sender = threading.Thread(target=self._send)
            self.sender.start()
            self.sender.join(timeout=0.3)  # unlocked, the review lands within this wait
        super().write(record)


def test_an_approve_and_a_review_at_the_same_moment_cannot_both_succeed(tmp_path: Path) -> None:
    plan_file = tmp_path / "plan.json"
    shutil.copy(Path(__file__).parents[2] / "examples" / "plan.json", plan_file)
    approval = ReviewArrivesDuringApprove(tmp_path / "approved.json", tmp_path)
    store = ThreadStore(tmp_path / "comments.json")
    drafts = DraftStore(tmp_path / "drafts.json")
    events = AgentEvents(
        LastEventStore(tmp_path / "last_event.json"), EventLog(tmp_path / "events.json")
    )
    app = FastAPI()
    app.include_router(approval_routes(store, drafts, plan_file, events, approval))

    approved = TestClient(app).post("/api/approve")
    assert approval.sender is not None
    approval.sender.join(timeout=5)

    assert approved.status_code == 200
    assert approval.review == {
        "status": 409,
        "body": {"errors": ["the plan is approved: a review can't be sent any more"]},
    }
    assert store.all() == []
    assert [d.text for d in drafts.all()] == ["late"]
