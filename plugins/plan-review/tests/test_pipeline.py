import json
from pathlib import Path

import pytest

from plan_review.pipeline import PipelineConfigError, load_pipeline


def write(tmp_path: Path, config: object) -> Path:
    path = tmp_path / "pipeline.json"
    path.write_text(json.dumps(config))
    return path


def test_missing_file_gives_the_defaults(tmp_path: Path) -> None:
    config = load_pipeline(tmp_path / "pipeline.json")

    assert config.checks == []
    assert config.review_rules == []
    assert config.branch == "{issue}-{slug}"
    assert config.viewer.open == "browser"
    assert config.max_review_rounds == 3


def test_project_values_are_read(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        {
            "checks": [{"name": "backend", "run": "backend/check.sh"}],
            "review_rules": ["Provider formats stay in backend/providers/"],
            "branch": "{issue}-{slug}",
            "viewer": {"open": "none"},
            "max_review_rounds": 2,
        },
    )

    config = load_pipeline(path)

    assert config.checks[0].run == "backend/check.sh"
    assert config.viewer.open == "none"
    assert config.max_review_rounds == 2


@pytest.mark.parametrize(
    ("config", "error"),
    [
        ({"chekcs": []}, "chekcs: Extra inputs are not permitted"),
        ({"viewer": {"open": "tab"}}, "viewer.open: Input should be 'browser' or 'none'"),
        ({"branch": "feature-{slug}"}, "branch: must contain {issue}"),
        ({"max_review_rounds": 0}, "max_review_rounds: Input should be greater than or equal to 1"),
    ],
)
def test_bad_config_is_reported_readably(tmp_path: Path, config: object, error: str) -> None:
    with pytest.raises(PipelineConfigError) as raised:
        load_pipeline(write(tmp_path, config))

    assert error in raised.value.errors[0]


def test_example_pipeline_config_is_valid_and_sets_every_field() -> None:
    example = Path(__file__).parents[1] / "examples" / "config.json"

    config = load_pipeline(example)

    assert config.model_fields_set == set(type(config).model_fields)


def test_grill_setting_is_page_chat_or_unset(tmp_path: Path) -> None:
    assert load_pipeline(tmp_path / "missing.json").grill is None
    assert load_pipeline(write(tmp_path, {"grill": "page"})).grill == "page"
    assert load_pipeline(write(tmp_path, {"grill": "chat"})).grill == "chat"

    with pytest.raises(PipelineConfigError) as raised:
        load_pipeline(write(tmp_path, {"grill": "tab"}))

    assert "grill: Input should be 'page' or 'chat'" in raised.value.errors[0]
