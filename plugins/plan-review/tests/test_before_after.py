"""The #53 and #56 plans kept twice: as plan-review 0.1.11 drew them, and in the new shape."""

import json
from pathlib import Path
from typing import Any

import pytest

from plan_review.cli import main
from plan_review.plan import load_plan, shape_problems

ROOT = Path(__file__).parents[1] / "examples" / "before-after"
RUNS = ["53", "56"]


def raw(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("run", RUNS)
def test_the_0_1_11_copies_still_load_and_are_in_the_old_shape(run: str) -> None:
    plan = load_plan(ROOT / run / "plan-0.1.11.json")

    assert plan.classes
    assert shape_problems(plan)
    assert all(c.side is None for c in plan.classes)


def test_the_converted_copies_pass_validate(capsys: pytest.CaptureFixture[str]) -> None:
    # Named one by one, not globbed: the 0.1.11 copies are meant to fail.
    for path in (ROOT / "53" / "plan.json", ROOT / "56" / "plan.json"):
        assert main(["validate", str(path)]) == 0, path
        assert capsys.readouterr().out.startswith("OK")


@pytest.mark.parametrize("run", RUNS)
def test_converting_changed_only_the_class_fields(run: str) -> None:
    old, new = raw(ROOT / run / "plan-0.1.11.json"), raw(ROOT / run / "plan.json")

    for key in old.keys() - {"classes"}:
        assert new[key] == old[key], key
    assert new.keys() == old.keys()
    assert [c["id"] for c in new["classes"]] == [c["id"] for c in old["classes"]]
    for was, now in zip(old["classes"], new["classes"], strict=True):
        assert [(m["id"], m["signature"], m["status"]) for m in now["members"]] == [
            (m["id"], m["signature"], m["status"]) for m in was["members"]
        ], was["id"]
        assert now["status"] == was["status"]
        if now["name"] != was["name"]:
            assert (was["kind"], now["kind"]) == ("function", "module"), was["id"]


@pytest.mark.parametrize("run", RUNS)
def test_the_converted_copies_have_both_sides(run: str) -> None:
    plan = load_plan(ROOT / run / "plan.json")
    by_id = {c.id: c for c in plan.classes}

    assert {c.side for c in plan.classes} == {"front", "back"}
    assert (by_id["class:QuestionCard"].side, by_id["class:QuestionCard"].kind) == (
        "front",
        "component",
    )
    assert by_id["class:GrillStore"].side == "back"
