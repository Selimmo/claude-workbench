import json
import time
from pathlib import Path

import pytest

from plan_review.cli import main
from plan_review.cli.runtime import Runtime
from plan_review.events.event_log import EventLog, wait_for_event
from plan_review.events.status import StatusStore


@pytest.fixture
def work(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    folder = tmp_path / ".plan-review" / "work" / "7"
    folder.mkdir(parents=True)
    return folder


def log_of(work: Path) -> EventLog:
    return EventLog(work / "events.json")


def printed(capsys: pytest.CaptureFixture[str]) -> list[dict[str, object]]:
    return [json.loads(line) for line in capsys.readouterr().out.splitlines()]


def test_wait_prints_a_waiting_event_at_once(
    work: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    log_of(work).record({"type": "approved"})

    started = time.monotonic()
    exit_code = main(["wait", "7", "--timeout", "30"])

    assert exit_code == 0
    assert printed(capsys) == [{"type": "approved", "seq": 1}]
    assert time.monotonic() - started < 5


def test_wait_returns_as_soon_as_an_event_arrives(work: Path) -> None:
    log = log_of(work)
    sleeps: list[float] = []

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        log.record({"type": "approved"})  # the owner acts while the agent waits

    event = wait_for_event(log, 30, now=lambda: 0.0, sleep=sleep, interval=0.05)

    assert event == {"type": "approved", "seq": 1}
    assert sleeps == [0.05]


def test_wait_times_out_with_a_timeout_event(work: Path) -> None:
    clock = [0.0]

    def sleep(seconds: float) -> None:
        clock[0] += seconds

    event = wait_for_event(log_of(work), 240, now=lambda: clock[0], sleep=sleep, interval=1)

    assert event == {"type": "timeout"}
    assert clock[0] >= 240


def test_wait_prints_the_timeout_and_exits_0(
    work: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(["wait", "7", "--timeout", "0"])

    assert exit_code == 0
    assert capsys.readouterr().out == '{"type":"timeout"}\n'


def test_wait_needs_no_running_server(work: Path, capsys: pytest.CaptureFixture[str]) -> None:
    log_of(work).record({"type": "grill_confirmed"})

    assert main(["wait", "7", "--timeout", "0"]) == 0
    assert printed(capsys) == [{"type": "grill_confirmed", "seq": 1}]


def test_wait_for_an_unknown_run_exits_1(work: Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["wait", "99", "--timeout", "0"])

    assert exit_code == 1
    assert "no .plan-review/work/99/" in capsys.readouterr().err


@pytest.mark.parametrize("bad", ["soon", "-1", "nan", "inf"])
def test_wait_refuses_a_bad_timeout(
    work: Path, capsys: pytest.CaptureFixture[str], bad: str
) -> None:
    exit_code = main(["wait", "7", "--timeout", bad])

    assert exit_code == 2
    assert "--timeout" in capsys.readouterr().err


def test_wait_reports_a_broken_log(work: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (work / "events.json").write_text("{ nope")

    exit_code = main(["wait", "7", "--timeout", "0"])

    assert exit_code == 1
    assert "events.json" in capsys.readouterr().err


def test_status_confirms_the_delivered_event(
    work: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    log_of(work).record({"type": "review_submitted", "comments": []})
    log_of(work).record({"type": "grill_confirmed"})
    main(["wait", "7", "--timeout", "0"])

    assert main(["status", "7", "Replying"]) == 0
    main(["wait", "7", "--timeout", "0"])

    assert [e["type"] for e in printed(capsys)] == ["review_submitted", "grill_confirmed"]


def test_status_clear_confirms_nothing(work: Path, capsys: pytest.CaptureFixture[str]) -> None:
    log_of(work).record({"type": "approved"})
    main(["wait", "7", "--timeout", "0"])

    main(["status", "7", "--clear"])
    main(["wait", "7", "--timeout", "0"])

    assert [e["type"] for e in printed(capsys)] == ["approved", "approved"]


def test_status_still_works_with_a_broken_log(
    work: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (work / "events.json").write_text("{ nope")

    exit_code = main(["status", "7", "Replying"])

    err = capsys.readouterr().err.strip().splitlines()
    assert exit_code == 0
    assert StatusStore(work / "status.json").get() is not None
    assert len(err) == 1
    assert "events.json" in err[0]


def test_wait_defaults_to_240_seconds(work: Path, capsys: pytest.CaptureFixture[str]) -> None:
    waited: list[float] = []

    def fake_wait(log: EventLog, timeout: float) -> dict[str, object]:
        waited.append(timeout)
        return {"type": "timeout"}

    assert main(["wait", "7"], runtime=Runtime(wait_for_event=fake_wait)) == 0

    assert waited == [240.0]
