"""The owner's unsent answers on the grill page."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from plan_review.grill_drafts import AnswerDraft, GrillDraftStore


def test_grill_drafts_are_kept_per_question_and_survive_a_restart(tmp_path: Path) -> None:
    path = tmp_path / "grill_drafts.json"
    store = GrillDraftStore(path)
    assert store.all() == {}

    store.put("q1", AnswerDraft(kind="choice", choice_id="a"))
    store.put("q2", AnswerDraft(kind="own", text="Mine"))
    store.put("q1", AnswerDraft(kind="ask", text="Why?"))  # replaces q1's draft

    assert {k: d.kind for k, d in GrillDraftStore(path).all().items()} == {
        "q1": "ask",
        "q2": "own",
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
        {"kind": "own", "text": "  "},
        {"kind": "ask"},
    ],
)
def test_a_draft_needs_what_its_kind_needs(fields: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        AnswerDraft.model_validate(fields)
