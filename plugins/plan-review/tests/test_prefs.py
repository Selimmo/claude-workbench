"""Recording and resolving the owner's grill mode."""

import json
from pathlib import Path

from plan_review.pipeline import PipelineConfig
from plan_review.prefs import Preferences, grill_mode, load_preferences, record
from plan_review.workdir import preferences_file


def test_recording_a_preference_writes_preferences_json_and_ignores_the_folder(
    tmp_path: Path,
) -> None:
    path = preferences_file(tmp_path)

    record(path, "page")

    assert path == tmp_path / ".plan-review" / "work" / "preferences.json"
    assert json.loads(path.read_text()) == {"grill": "page"}
    assert (tmp_path / ".plan-review" / "work" / ".gitignore").read_text() == "*\n"
    assert load_preferences(path).grill == "page"


def test_recording_keeps_a_gitignore_the_project_already_has(tmp_path: Path) -> None:
    ignore = tmp_path / ".plan-review" / "work" / ".gitignore"
    ignore.parent.mkdir(parents=True)
    ignore.write_text("*\n!decisions.md\n")

    record(preferences_file(tmp_path), "chat")

    assert ignore.read_text() == "*\n!decisions.md\n"


def test_pipeline_grill_wins_over_the_recorded_preference() -> None:
    assert grill_mode(PipelineConfig(grill="chat"), Preferences(grill="page")) == "chat"
    assert grill_mode(PipelineConfig(), Preferences(grill="page")) == "page"
    assert grill_mode(PipelineConfig(), Preferences()) is None


def test_no_preferences_file_means_nothing_chosen(tmp_path: Path) -> None:
    assert load_preferences(tmp_path / "preferences.json").grill is None
