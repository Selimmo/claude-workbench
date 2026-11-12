"""decisions.md, written from a confirmed grill in the format /ship wrote by hand."""

from pathlib import Path

from plan_review.grill.decisions_md import decisions_markdown
from plan_review.grill.state import Decision, GrillState
from plan_review.grill.store import load_grill

EXAMPLE = Path(__file__).parents[2] / "examples" / "grill.json"

TODAYS_FORMAT = """\
# Decisions for #53: Add hints to the quiz

## Scoring
- **A hint costs 2 points, never below zero**: Costs points, floored at zero. A floor was asked for.

## Content
- **Hints are written with the question**: Authors write them. A model call per hint is too costly.

## Out of scope
- Hints for timed rounds
- Translating hints
"""


def test_decisions_md_comes_out_in_todays_format() -> None:
    assert decisions_markdown(load_grill(EXAMPLE), "#53") == TODAYS_FORMAT


def test_replaced_decisions_and_an_empty_out_of_scope_are_left_out() -> None:
    def make(did: str, topic: str, replaces: str | None = None) -> Decision:
        return Decision(id=did, topic=topic, decision=f"Do {did}", choice="Yes", replaces=replaces)

    state = GrillState(
        title="T",
        decisions=[make("d1", "A"), make("d2", "B"), make("d3", "B", replaces="d1")],
    )

    text = decisions_markdown(state, "PROJ-1")

    assert text == ("# Decisions for PROJ-1: T\n\n## B\n- **Do d3**: Yes\n- **Do d2**: Yes\n")
    assert "Out of scope" not in text


def test_a_trailing_period_on_the_choice_is_not_doubled() -> None:
    state = GrillState(
        title="T",
        decisions=[Decision(id="d1", topic="A", decision="Do it", choice="Yes.", why="Cheap.")],
    )

    assert (
        decisions_markdown(state, "#1")
        == "# Decisions for #1: T\n\n## A\n- **Do it**: Yes. Cheap.\n"
    )
