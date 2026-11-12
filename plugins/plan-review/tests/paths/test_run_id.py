"""A run id names a work folder: an issue key, or a dated prompt name."""

import pytest

from plan_review.paths.run_id import RUN_ID, InvalidRunId, check_run_id, label


@pytest.mark.parametrize("text", ["42", "PROJ-123", "ENG-42", "add-dark-mode-2026-11-05"])
def test_a_run_id_is_a_tracker_key_or_a_dated_name(text: str) -> None:
    assert check_run_id(text) == text


@pytest.mark.parametrize("text", ["#42", "", ".hidden", "../x", "a/b", "a b", "a\\b"])
def test_anything_else_is_rejected_as_a_run_id(text: str) -> None:
    with pytest.raises(InvalidRunId) as error:
        check_run_id(text)

    assert f"'{text}'" in str(error.value)
    assert RUN_ID.pattern in str(error.value)


def test_a_numeric_id_is_labelled_with_a_hash_and_any_other_id_as_written() -> None:
    assert label("42") == "#42"
    assert label("PROJ-123") == "PROJ-123"
    assert label("add-dark-mode-2026-11-05") == "add-dark-mode-2026-11-05"
