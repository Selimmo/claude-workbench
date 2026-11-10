"""The owner's unsent answers on the grill page."""

from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import ValidationError

from plan_review.grill.drafts import AnswerDraft, GrillDraftStore
from plan_review.utils.json_files import BrokenFile


def test_grill_drafts_are_kept_per_question_and_survive_a_restart(tmp_path: Path) -> None:
    path = tmp_path / "grill_drafts.json"
    store = GrillDraftStore(path)
    assert store.all() == {}

    store.put("q1", AnswerDraft(kind="choice", choice_id="a"))
    store.put("q2", AnswerDraft(kind="other", text="Mine"))
    store.put("q1", AnswerDraft(kind="other", text="Why?"))  # replaces q1's draft

    assert {k: d.kind for k, d in GrillDraftStore(path).all().items()} == {
        "q1": "other",
        "q2": "other",
    }

    store.discard("q2")
    assert list(GrillDraftStore(path).all()) == ["q1"]

    store.put("q3", AnswerDraft(kind="choice", choice_id="b"))
    with store.held():
        store.clear({"q1"})  # the held lock is reused, not taken twice
    assert list(GrillDraftStore(path).all()) == ["q3"]


@pytest.mark.parametrize(
    "fields",
    [
        {"kind": "choice"},
        {"kind": "own", "text": "Mine"},
        {"kind": "ask", "text": "Why?"},
    ],
)
def test_a_draft_needs_what_its_kind_needs(fields: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        AnswerDraft.model_validate(fields)


@pytest.mark.parametrize("fields", [{"kind": "other"}, {"kind": "other", "text": ""}])
def test_an_empty_other_draft_is_valid_while_the_owner_types(fields: dict[str, str]) -> None:
    assert AnswerDraft.model_validate(fields).kind == "other"


def test_a_broken_grill_drafts_json_is_reported_and_left_as_it_is(tmp_path: Path) -> None:
    path = tmp_path / "grill_drafts.json"
    path.write_bytes(b"{bad")
    store = GrillDraftStore(path)
    named = [f"{path.as_posix()}: Invalid JSON: key must be a string at line 1 column 2"]
    changes: list[Callable[[], object]] = [
        store.all,
        lambda: store.put("q1", AnswerDraft(kind="choice", choice_id="a")),
        lambda: store.clear({"q1"}),
        lambda: store.discard("q1"),
    ]

    for change in changes:
        with pytest.raises(BrokenFile) as error:
            change()
        assert error.value.errors == named

    assert path.read_bytes() == b"{bad"
