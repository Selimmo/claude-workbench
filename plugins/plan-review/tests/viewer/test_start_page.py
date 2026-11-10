"""Which page the viewer opens on: the plan's, or before a plan, the grill's."""

import json
from pathlib import Path

import pytest

from plan_review.paths.run_paths import RunPaths
from plan_review.plan.plan import PlanFileError
from plan_review.viewer.start_page import start_page

VALID_PLAN = {
    "issue": {"id": "7", "kind": "issue", "title": "Add hints"},
    "summary": "Hint button.",
}


@pytest.fixture
def paths(tmp_path: Path) -> RunPaths:
    return RunPaths(tmp_path)


def test_the_viewer_opens_on_the_plan_when_there_is_one(paths: RunPaths) -> None:
    paths.plan.write_text(json.dumps(VALID_PLAN))
    assert start_page(paths) == ""

    paths.grill.write_text("{}")
    assert start_page(paths) == ""


def test_before_a_plan_the_viewer_opens_on_the_grill(paths: RunPaths) -> None:
    paths.grill.write_text("{}")

    assert start_page(paths) == "grill"


def test_with_neither_a_plan_nor_a_grill_start_page_raises_the_missing_plan(
    paths: RunPaths,
) -> None:
    with pytest.raises(PlanFileError) as raised:
        start_page(paths)

    assert raised.value.missing
    assert raised.value.errors == [f"{paths.plan.as_posix()}: file not found"]


def test_an_invalid_plan_is_an_error_even_with_a_grill(paths: RunPaths) -> None:
    paths.plan.write_text("{}")
    paths.grill.write_text("{}")

    with pytest.raises(PlanFileError) as raised:
        start_page(paths)

    assert not raised.value.missing
