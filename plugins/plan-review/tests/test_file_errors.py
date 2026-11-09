from pathlib import Path

import pytest
from pydantic import BaseModel, TypeAdapter, ValidationError

from plan_review.file_errors import BrokenFile, named_errors, read_file
from plan_review.threads import Thread

PLAN = Path(".plan-review/work/42/plan.json")


class _Two(BaseModel):
    a: int
    b: int


def test_named_errors_put_the_files_path_before_each_line() -> None:
    with pytest.raises(ValidationError) as caught:
        _Two.model_validate({})

    assert named_errors(PLAN, caught.value) == [
        ".plan-review/work/42/plan.json: a: Field required",
        ".plan-review/work/42/plan.json: b: Field required",
    ]


def test_read_file_gives_none_without_a_file_and_the_value_when_it_parses(tmp_path: Path) -> None:
    adapter = TypeAdapter(list[int])

    assert read_file(tmp_path / "nums.json", adapter) is None

    (tmp_path / "nums.json").write_text("[1, 2]")
    assert read_file(tmp_path / "nums.json", adapter) == [1, 2]


def test_read_file_of_a_broken_file_raises_broken_file_with_named_lines(tmp_path: Path) -> None:
    path = tmp_path / "comments.json"
    path.write_text("{bad")
    with pytest.raises(BrokenFile) as bad_json:
        read_file(path, TypeAdapter(list[Thread]))
    assert bad_json.value.errors == [
        f"{path.as_posix()}: Invalid JSON: key must be a string at line 1 column 2"
    ]

    path.write_text("[1]")
    with pytest.raises(BrokenFile) as bad_shape:
        read_file(path, TypeAdapter(list[Thread]))
    assert bad_shape.value.errors == [f"{path.as_posix()}: 0: Input should be an object"]
