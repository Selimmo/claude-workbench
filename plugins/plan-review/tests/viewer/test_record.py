import json
from pathlib import Path

import pytest

from plan_review.viewer.record import ViewerInfo, ViewerRecord


def test_a_written_viewer_record_reads_back(tmp_path: Path) -> None:
    record = ViewerRecord(tmp_path)
    assert record.read() is None

    info = ViewerInfo(run_id="7", pid=1, port=2, token="t")
    record.write(info)

    assert record.read() == info
    assert json.loads((tmp_path / "viewer.json").read_text()) == {
        "run_id": "7",
        "pid": 1,
        "port": 2,
        "token": "t",
    }
    assert not list(tmp_path.glob(".viewer.json.*"))  # no temporary file left behind


@pytest.mark.parametrize(
    ("content", "left"),
    [
        (json.dumps({"token": "mine"}), None),
        (json.dumps({"token": "newer"}), json.dumps({"token": "newer"})),
        ("{ not json", None),
        ("[]", None),
    ],
)
def test_a_viewer_record_is_removed_only_while_it_is_still_mine(
    tmp_path: Path, content: str, left: str | None
) -> None:
    file = tmp_path / "viewer.json"
    file.write_text(content)

    ViewerRecord(tmp_path).remove_if_mine("mine")

    assert (file.read_text() if file.exists() else None) == left


def test_removing_a_record_that_is_not_there_is_no_error(tmp_path: Path) -> None:
    ViewerRecord(tmp_path).remove_if_mine("mine")
