"""SocketWaiting and PollingWaiting: the texts for how an agent waits for the owner."""

from plan_review.harness.waiting import PollingWaiting, SocketWaiting


def test_socket_waiting_listens_on_the_viewer_socket_with_the_named_listener() -> None:
    waiting = SocketWaiting(listener="Watcher")

    for text in (waiting.grill_listen, waiting.review_listen):
        assert "**Watcher**" in text
        assert "ws://127.0.0.1:<port>/events" in text
    assert "stop the Watcher and the server task" in waiting.stop_viewer
    assert waiting.ignore_repeat == "ignore it."


def test_polling_waiting_waits_with_the_wait_command() -> None:
    waiting = PollingWaiting()

    for text in (waiting.grill_listen, waiting.review_listen):
        assert "`plan-review wait ID --timeout 240`" in text
    assert waiting.stop_viewer == "run `plan-review stop ID`"
    assert waiting.abort_viewer == "run `plan-review stop ID`"
    assert "plan-review status ID" in waiting.ignore_repeat


def test_polling_waiting_takes_its_wait_in_seconds() -> None:
    assert "--timeout 30" in PollingWaiting(wait_seconds=30).grill_listen
    assert "--timeout 30" in PollingWaiting(wait_seconds=30).review_listen
