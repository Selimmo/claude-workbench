import json
from pathlib import Path

import pytest

from plan_review.event_log import EventLog
from plan_review.file_errors import BrokenFile

REVIEW = {"type": "review_submitted", "comments": []}
APPROVED = {"type": "approved"}


@pytest.fixture
def log(tmp_path: Path) -> EventLog:
    return EventLog(tmp_path / "events.json")


def types(event: dict[str, object] | None) -> object:
    return None if event is None else event["type"]


def test_recorded_events_are_kept_in_order_with_a_seq(log: EventLog, tmp_path: Path) -> None:
    log.record({"type": "a"})
    log.record({"type": "b"})

    saved = json.loads((tmp_path / "events.json").read_text())
    assert [(e["seq"], e["event"]["type"]) for e in saved["events"]] == [(1, "a"), (2, "b")]


def test_offer_returns_the_oldest_unhandled_event(log: EventLog) -> None:
    log.record({"type": "a"})
    log.record({"type": "b"})

    event = log.offer()

    assert event == {"type": "a", "seq": 1}


def test_offer_with_nothing_waiting_returns_none_and_creates_no_file(
    log: EventLog, tmp_path: Path
) -> None:
    assert log.offer() is None
    assert list(tmp_path.iterdir()) == []


def test_offer_with_an_empty_log_returns_none(log: EventLog, tmp_path: Path) -> None:
    (tmp_path / "events.json").write_text('{"events": []}')

    assert log.offer() is None


def test_confirm_with_no_log_creates_no_file(log: EventLog, tmp_path: Path) -> None:
    log.confirm()

    assert list(tmp_path.iterdir()) == []


def test_offer_repeats_an_event_until_it_is_confirmed(log: EventLog) -> None:
    log.record({"type": "a"})

    assert log.offer() == log.offer() == {"type": "a", "seq": 1}


def test_confirm_moves_on_to_the_next_event(log: EventLog) -> None:
    log.record({"type": "a"})
    log.record({"type": "b"})
    log.offer()

    log.confirm()

    assert log.offer() == {"type": "b", "seq": 2}
    log.confirm()
    assert log.offer() is None


def test_confirm_marks_only_what_was_delivered(log: EventLog) -> None:
    log.record({"type": "a"})
    log.offer()
    log.record({"type": "b"})  # arrives after delivery, before the status

    log.confirm()

    assert log.offer() == {"type": "b", "seq": 2}


def test_confirm_with_nothing_delivered_does_nothing(log: EventLog) -> None:
    log.record({"type": "a"})
    log.confirm()  # "Plan ready for review": nothing was delivered yet

    assert log.offer() == {"type": "a", "seq": 1}


def test_many_confirms_for_one_event_count_once(log: EventLog) -> None:
    log.record({"type": "a"})
    log.record({"type": "b"})
    log.offer()

    for _ in range(4):
        log.confirm()

    assert log.offer() == {"type": "b", "seq": 2}


def test_a_leftover_temp_file_is_ignored(log: EventLog, tmp_path: Path) -> None:
    (tmp_path / ".events.json.abc.tmp").write_text("{ half")
    log.record({"type": "a"})

    assert log.offer() == {"type": "a", "seq": 1}


def test_a_broken_log_is_reported_and_never_replaced(tmp_path: Path) -> None:
    path = tmp_path / "events.json"
    path.write_text("{ not json")
    log = EventLog(path)

    with pytest.raises(BrokenFile, match="events.json"):
        log.record({"type": "a"})
    with pytest.raises(BrokenFile, match="events.json"):
        log.offer()

    assert path.read_text() == "{ not json"


def test_a_log_that_cannot_be_written_fails_the_check(tmp_path: Path) -> None:
    path = tmp_path / "events.json"
    path.mkdir()  # exists, and no file can replace it

    with pytest.raises(BrokenFile, match="events.json"):
        EventLog(path).check()


def test_a_log_that_cannot_be_written_fails_the_record_by_name(tmp_path: Path) -> None:
    path = tmp_path / "events.json"
    path.mkdir()

    with pytest.raises(BrokenFile, match="events.json"):
        EventLog(path).record({"type": "a"})


def test_two_runs_have_separate_logs(tmp_path: Path) -> None:
    (tmp_path / "1").mkdir()
    (tmp_path / "2").mkdir()
    EventLog(tmp_path / "1" / "events.json").record({"type": "a"})

    assert EventLog(tmp_path / "2" / "events.json").offer() is None


def approve(tmp_path: Path) -> None:
    (tmp_path / "approved.json").write_text("{}")


def test_an_approval_ahead_of_a_review_is_withdrawn(log: EventLog, tmp_path: Path) -> None:
    approve(tmp_path)
    log.record(APPROVED)
    log.record(REVIEW)
    event = log.offer()

    assert event is not None
    assert event["type"] == "review_submitted"
    assert event["approval_withdrawn"] is True
    assert not (tmp_path / "approved.json").exists()
    log.confirm()
    assert log.offer() is None


def test_a_review_ahead_of_an_approval_withdraws_it_too(log: EventLog, tmp_path: Path) -> None:
    log.record(REVIEW)
    approve(tmp_path)
    log.record(APPROVED)

    event = log.offer()

    assert event is not None
    assert (event["type"], event["approval_withdrawn"]) == ("review_submitted", True)
    assert not (tmp_path / "approved.json").exists()
    log.confirm()
    assert log.offer() is None


def test_a_withdrawal_is_offered_again_until_it_is_confirmed(log: EventLog, tmp_path: Path) -> None:
    approve(tmp_path)
    log.record(APPROVED)
    log.record(REVIEW)

    first, second = log.offer(), log.offer()  # the agent crashed before its status

    assert first is not None and second is not None
    assert first["approval_withdrawn"] is True
    assert second["approval_withdrawn"] is True
    log.confirm()
    assert log.offer() is None


def test_a_new_approval_after_a_withdrawal_is_offered(log: EventLog, tmp_path: Path) -> None:
    approve(tmp_path)
    log.record(APPROVED)
    log.record(REVIEW)
    log.offer()
    log.confirm()

    log.record(APPROVED)

    assert log.offer() == {"type": "approved", "seq": 3}


def test_a_withdrawal_copes_with_the_approval_file_already_gone(log: EventLog) -> None:
    log.record(APPROVED)  # no approved.json: lost to a crash and a retry
    log.record(REVIEW)

    event = log.offer()

    assert event is not None
    assert event["approval_withdrawn"] is True


def test_the_first_of_two_waiting_reviews_carries_the_withdrawal(log: EventLog) -> None:
    log.record(REVIEW)
    log.record(REVIEW)
    log.record(APPROVED)

    event = log.offer()

    assert event is not None
    assert (event["seq"], event["approval_withdrawn"]) == (1, True)


def test_a_review_alone_does_not_withdraw_an_approval_already_handled(
    log: EventLog, tmp_path: Path
) -> None:
    approve(tmp_path)
    log.record(REVIEW)

    event = log.offer()

    assert event is not None
    assert "approval_withdrawn" not in event
    assert (tmp_path / "approved.json").exists()
