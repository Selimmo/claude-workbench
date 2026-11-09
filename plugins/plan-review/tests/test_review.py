import threading
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from plan_review.drafts import DraftNotFound, DraftStore
from plan_review.events import AgentEvents
from plan_review.last_event import LastEventStore
from plan_review.review import review_routes
from plan_review.threads import Thread, ThreadStore


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
        review_routes(threads, drafts, AgentEvents(LastEventStore(tmp_path / "last_event.json")))
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
        review_routes(threads, drafts, AgentEvents(LastEventStore(tmp_path / "last_event.json")))
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
