from pathlib import Path

import pytest

from plan_review.status import StatusStore


@pytest.fixture
def store(tmp_path: Path) -> StatusStore:
    return StatusStore(tmp_path / "status.json")


def test_no_status_until_one_is_set(store: StatusStore) -> None:
    assert store.get() is None


def test_the_latest_text_wins_and_is_in_progress(store: StatusStore) -> None:
    store.set("Review received (3 comments)")
    store.set("Answering questions")

    status = store.get()
    assert status is not None
    assert (status.text, status.done) == ("Answering questions", False)


def test_done_marks_the_status_finished(store: StatusStore) -> None:
    store.set("Architect revising")
    store.set("Plan updated: 2 classes changed", done=True)

    status = store.get()
    assert status is not None
    assert (status.text, status.done) == ("Plan updated: 2 classes changed", True)


def test_the_status_persists_for_another_store_on_the_same_file(tmp_path: Path) -> None:
    StatusStore(tmp_path / "status.json").set("Answering questions")

    assert StatusStore(tmp_path / "status.json").get() is not None


def test_clear_removes_the_status(store: StatusStore) -> None:
    store.set("Answering questions")

    store.clear()

    assert store.get() is None


@pytest.mark.parametrize("text", ["", "  "])
def test_blank_status_is_refused(store: StatusStore, text: str) -> None:
    with pytest.raises(ValueError, match="empty"):
        store.set(text)
