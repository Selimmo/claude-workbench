from pathlib import Path

import pytest

from plan_review.file_errors import BrokenFile
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


def test_setting_a_status_over_a_broken_status_json_moves_it_to_status_json_broken(
    tmp_path: Path,
) -> None:
    path = tmp_path / "status.json"
    store = StatusStore(path)
    path.write_bytes(b"{bad")

    with pytest.raises(BrokenFile) as error:
        store.get()
    assert error.value.errors == [
        f"{path.as_posix()}: Invalid JSON: key must be a string at line 1 column 2"
    ]

    store.set("working")

    status = store.get()
    assert status is not None
    assert status.text == "working"
    assert (tmp_path / "status.json.broken").read_bytes() == b"{bad"

    store.set("again")  # a readable status.json is replaced as before
    assert (tmp_path / "status.json.broken").read_bytes() == b"{bad"


def test_a_readable_status_json_leaves_no_broken_copy(tmp_path: Path) -> None:
    store = StatusStore(tmp_path / "status.json")
    store.set("one")
    store.set("two")

    assert not (tmp_path / "status.json.broken").exists()


def test_clearing_a_broken_status_json_moves_it_aside_replacing_an_older_copy(
    tmp_path: Path,
) -> None:
    path = tmp_path / "status.json"
    store = StatusStore(path)
    assert store.set_aside() is None  # nothing there

    store.set("fine")
    assert store.set_aside() is None  # it reads
    (tmp_path / "status.json.broken").write_bytes(b"older")
    path.write_bytes(b"[1]")

    store.clear()

    assert (tmp_path / "status.json.broken").read_bytes() == b"[1]"
    assert not path.exists()

    path.write_bytes(b"{bad")
    assert store.set_aside() == tmp_path / "status.json.broken"
