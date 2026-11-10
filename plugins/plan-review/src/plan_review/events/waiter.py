"""`plan-review wait`: block until the agent has an event to handle."""

import time
from collections.abc import Callable
from typing import Any

from plan_review.events.event_log import EventLog


def wait_for_event(
    log: EventLog,
    timeout: float,
    *,
    now: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    interval: float = 0.5,
) -> dict[str, Any]:
    """The next event, as soon as there is one; `{"type": "timeout"}` after `timeout` seconds."""
    deadline = now() + timeout
    while True:
        event = log.offer()
        if event is not None:
            return event
        if now() >= deadline:
            return {"type": "timeout"}
        sleep(interval)
