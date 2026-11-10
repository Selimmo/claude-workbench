import threading
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from plan_review.events.event_log import EventLog
from plan_review.events.events import AgentEvents
from plan_review.events.last_event import LastEventStore
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


def review_app(tmp_path: Path, threads: ThreadStore, drafts: DraftStore) -> TestClient:
    app = FastAPI()
    events = AgentEvents(
        LastEventStore(tmp_path / "last_event.json"), EventLog(tmp_path / "events.json")
    )
    app.include_router(review_routes(threads, drafts, events))
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
