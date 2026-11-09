import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi import WebSocket

from plan_review.event_log import EventLog
from plan_review.events import AgentEvents, Subscribers
from plan_review.file_errors import BrokenFile
from plan_review.last_event import LastEventStore


class FakeSocket:
    def __init__(self, on_send: Callable[[], None] | None = None) -> None:
        self.sent: list[dict[str, Any]] = []
        self._on_send = on_send

    async def send_json(self, message: dict[str, Any]) -> None:
        if self._on_send is not None:
            self._on_send()
        self.sent.append(message)


def events_in(tmp_path: Path) -> tuple[AgentEvents, EventLog]:
    log = EventLog(tmp_path / "events.json")
    return AgentEvents(LastEventStore(tmp_path / "last_event.json"), log), log


def test_send_records_then_pushes(tmp_path: Path) -> None:
    events, log = events_in(tmp_path)
    in_log_when_pushed: list[bool] = []
    socket = FakeSocket(lambda: in_log_when_pushed.append(log.offer() is not None))
    events.add(socket)  # pyright: ignore[reportArgumentType]

    asyncio.run(events.send({"type": "approved"}))

    assert in_log_when_pushed == [True]  # already on disk when the push goes out
    assert socket.sent == [{"type": "approved"}]


def test_a_broken_log_is_reported_and_nothing_is_pushed(tmp_path: Path) -> None:
    (tmp_path / "events.json").write_text("{ nope")
    events, _ = events_in(tmp_path)
    socket = FakeSocket()
    events.add(socket)  # pyright: ignore[reportArgumentType]

    with pytest.raises(BrokenFile, match="events.json"):
        asyncio.run(events.send({"type": "approved"}))

    assert socket.sent == []


def test_an_event_the_log_refused_is_not_kept_for_a_resend(tmp_path: Path) -> None:
    (tmp_path / "events.json").write_text("{ nope")
    events, _ = events_in(tmp_path)

    with pytest.raises(BrokenFile):
        events.record({"type": "approved"})

    assert not (tmp_path / "last_event.json").exists()


def test_a_broken_kept_event_does_not_stop_the_log(tmp_path: Path) -> None:
    (tmp_path / "last_event.json").write_text("{ nope")
    events, log = events_in(tmp_path)

    events.record({"type": "approved"})

    assert log.offer() == {"type": "approved", "seq": 1}


def test_a_kept_event_that_cannot_be_written_does_not_fail_the_record(tmp_path: Path) -> None:
    (tmp_path / "last_event.json").mkdir()
    events, log = events_in(tmp_path)

    events.record({"type": "approved"})

    assert log.offer() == {"type": "approved", "seq": 1}


def test_resend_pushes_without_adding_to_the_log(tmp_path: Path) -> None:
    events, log = events_in(tmp_path)
    socket = FakeSocket()
    events.add(socket)  # pyright: ignore[reportArgumentType]
    events.record({"type": "approved"})

    asyncio.run(events.resend({"type": "approved"}))

    assert socket.sent == [{"type": "approved"}]
    assert log.offer() == {"type": "approved", "seq": 1}
    log.confirm()
    assert log.offer() is None


def test_subscribers_count_open_sockets() -> None:
    subscribers = Subscribers()
    one: WebSocket = FakeSocket()  # pyright: ignore[reportAssignmentType]
    two: WebSocket = FakeSocket()  # pyright: ignore[reportAssignmentType]

    subscribers.add(one)
    subscribers.add(two)
    assert subscribers.count == 2
    subscribers.remove(one)
    assert subscribers.count == 1
