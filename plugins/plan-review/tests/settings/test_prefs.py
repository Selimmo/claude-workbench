"""Recording and resolving the owner's grill mode."""

import json
from pathlib import Path

import pytest

from plan_review.paths.workdir import preferences_file
from plan_review.settings.migration import config_source, preferences_source
from plan_review.settings.pipeline_config import PipelineConfig, PipelineConfigError
from plan_review.settings.prefs import (
    GrillChoice,
    Preferences,
    PreferencesError,
    chosen_grill_mode,
    grill_mode,
    load_preferences,
    record,
)


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


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_the_project_config_grill_wins_over_the_saved_choice(tmp_path: Path) -> None:
    write(config_source(tmp_path).path, '{"grill": "chat"}')
    write(preferences_source(tmp_path).path, '{"grill": "page"}')

    assert chosen_grill_mode(tmp_path) == GrillChoice(mode="chat", hints=())


def test_the_saved_choice_is_used_when_the_config_sets_none(tmp_path: Path) -> None:
    write(preferences_source(tmp_path).path, '{"grill": "page"}')
    assert chosen_grill_mode(tmp_path).mode == "page"

    write(config_source(tmp_path).path, "{}")
    assert chosen_grill_mode(tmp_path).mode == "page"


def test_with_neither_a_setting_nor_a_saved_choice_nothing_is_chosen(tmp_path: Path) -> None:
    assert chosen_grill_mode(tmp_path) == GrillChoice(mode=None, hints=())


def test_old_files_are_read_and_their_move_hints_come_in_order(tmp_path: Path) -> None:
    write(tmp_path / ".claude" / "pipeline.json", "{}")
    write(tmp_path / ".claude" / "work" / "preferences.json", '{"grill": "chat"}')
    config_hint = config_source(tmp_path).move_hint
    preferences_hint = preferences_source(tmp_path).move_hint

    choice = chosen_grill_mode(tmp_path)

    assert choice.mode == "chat"
    assert choice.hints == (config_hint, preferences_hint)
    assert None not in choice.hints


def test_a_broken_config_raises_before_the_preferences_are_read(tmp_path: Path) -> None:
    config = write(config_source(tmp_path).path, "{bad")
    write(preferences_source(tmp_path).path, "{bad")

    with pytest.raises(PipelineConfigError) as raised:
        chosen_grill_mode(tmp_path)

    assert raised.value.errors
    assert all(line.startswith(config.as_posix()) for line in raised.value.errors)
    assert not any("preferences.json" in line for line in raised.value.errors)


@pytest.mark.parametrize("text", ["{bad", '{"grill": "pagex"}'])
def test_a_broken_preferences_file_raises_its_named_lines(tmp_path: Path, text: str) -> None:
    old = write(tmp_path / ".claude" / "work" / "preferences.json", text)

    with pytest.raises(PreferencesError) as raised:
        chosen_grill_mode(tmp_path)

    assert raised.value.errors
    assert all(line.startswith(old.as_posix()) for line in raised.value.errors)
