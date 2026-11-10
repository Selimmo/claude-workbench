import json
from pathlib import Path

import pytest

from plan_review.review.approval_file import ApprovalFile, ApprovalRecord
from plan_review.utils.json_files import BrokenFile


def test_no_approval_file_reads_as_none(tmp_path: Path) -> None:
    path = tmp_path / "approved.json"

    assert ApprovalFile(path).read() is None
    assert not path.exists()


def test_a_written_approval_reads_back(tmp_path: Path) -> None:
    path = tmp_path / "approved.json"
    record = ApprovalRecord(approved_at="2026-01-01T00:00:00+00:00", plan_sha256="abc")
    approval = ApprovalFile(path)

    approval.write(record)

    assert approval.read() == record
    assert set(json.loads(path.read_text("utf-8"))) == {
        "approved_at",
        "plan_sha256",
    }
    assert [p.name for p in tmp_path.iterdir()] == ["approved.json"]


def test_writing_over_a_broken_approval_file_is_refused_and_leaves_it(tmp_path: Path) -> None:
    path = tmp_path / "approved.json"
    path.write_bytes(b"{bad")
    approval = ApprovalFile(path)

    with pytest.raises(BrokenFile) as read_error:
        approval.read()
    with pytest.raises(BrokenFile) as write_error:
        approval.write(ApprovalRecord(approved_at="t", plan_sha256="abc"))

    for error in (read_error, write_error):
        assert all(line.startswith(path.as_posix()) for line in error.value.errors)
    assert path.read_bytes() == b"{bad"
