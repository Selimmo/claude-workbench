from datetime import UTC, datetime
from pathlib import Path

import pytest

from plan_review.file_errors import BrokenFile
from plan_review.last_event import LastEvent, LastEventStore, answered
from plan_review.status import Status


@pytest.fixture
def store(tmp_path: Path) -> LastEventStore:
    return LastEventStore(tmp_path / "last_event.json")


def test_no_event_is_kept_until_one_is_sent(store: LastEventStore) -> None:
    assert store.get() is None


def test_a_kept_event_is_read_back_unchanged_with_when_it_was_sent(tmp_path: Path) -> None:
    event = {"type": "review_submitted", "comments": [{"type": "comment", "text": "why?"}]}
    before = datetime.now(UTC)

    LastEventStore(tmp_path / "last_event.json").keep(event)

    last = LastEventStore(tmp_path / "last_event.json").get()
    assert last is not None
    assert last.event == event
    assert last.sent_at.tzinfo is not None
    assert last.sent_at >= before


def test_keeping_again_replaces_the_event_and_re_stamps_it(store: LastEventStore) -> None:
    first = store.keep({"type": "review_submitted", "comments": []})
    second = store.keep({"type": "approved"})

    last = store.get()
    assert last is not None
    assert last.event == {"type": "approved"}
    assert last.sent_at == second.sent_at
    assert last.sent_at >= first.sent_at


def _status(at: datetime) -> Status:
    return Status(text="Working", at=at)


def _last(sent_at: datetime) -> LastEvent:
    return LastEvent(event={"type": "approved"}, sent_at=sent_at)


def test_no_status_is_not_answered() -> None:
    assert not answered(None, _last(datetime(2026, 11, 4, 10, 1, tzinfo=UTC)))


def test_a_status_from_before_the_event_is_not_answered() -> None:
    status = _status(datetime(2026, 11, 4, 10, 0, tzinfo=UTC))

    assert not answered(status, _last(datetime(2026, 11, 4, 10, 1, tzinfo=UTC)))


def test_a_status_after_the_event_is_answered() -> None:
    status = _status(datetime(2026, 11, 4, 10, 2, tzinfo=UTC))

    assert answered(status, _last(datetime(2026, 11, 4, 10, 1, tzinfo=UTC)))


def test_a_broken_last_event_json_is_reported_and_never_replaced(tmp_path: Path) -> None:
    path = tmp_path / "last_event.json"
    path.write_bytes(b"{bad")
    store = LastEventStore(path)
    named = [f"{path.as_posix()}: Invalid JSON: key must be a string at line 1 column 2"]

    with pytest.raises(BrokenFile) as read:
        store.get()
    with pytest.raises(BrokenFile) as kept:
        store.keep({"type": "approved"})

    assert read.value.errors == kept.value.errors == named
    assert path.read_bytes() == b"{bad"
