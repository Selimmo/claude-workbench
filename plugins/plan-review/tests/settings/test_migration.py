"""Old `.claude/` files are read when they are the only ones; the grill choice moves once."""

import json
from pathlib import Path
from typing import Any

import pytest

from plan_review.settings.migration import config_source, move_grill_preference

NEW_CONFIG = Path(".plan-review") / "config.json"
OLD_CONFIG = Path(".claude") / "pipeline.json"
NEW_PREFS = Path(".plan-review") / "work" / "preferences.json"
OLD_PREFS = Path(".claude") / "work" / "preferences.json"


def touch(root: Path, relative: Path) -> None:
    (root / relative).parent.mkdir(parents=True, exist_ok=True)
    (root / relative).write_text("{}")


def test_config_source_with_neither_file_is_the_new_path_with_no_hint(tmp_path: Path) -> None:
    source = config_source(tmp_path)

    assert source.path == tmp_path / NEW_CONFIG
    assert source.move_hint is None
    assert list(tmp_path.iterdir()) == []


def test_config_source_prefers_the_new_file_when_both_exist(tmp_path: Path) -> None:
    touch(tmp_path, NEW_CONFIG)
    touch(tmp_path, OLD_CONFIG)

    source = config_source(tmp_path)

    assert source.path == tmp_path / NEW_CONFIG
    assert source.move_hint is None


def test_config_source_uses_the_old_file_when_it_is_the_only_one(tmp_path: Path) -> None:
    touch(tmp_path, OLD_CONFIG)

    source = config_source(tmp_path)

    assert source.path == tmp_path / OLD_CONFIG
    assert source.move_hint is not None
    assert "\n" not in source.move_hint
    assert ".claude/pipeline.json" in source.move_hint
    assert ".plan-review/config.json" in source.move_hint


def write(root: Path, relative: Path, text: str) -> Path:
    (root / relative).parent.mkdir(parents=True, exist_ok=True)
    (root / relative).write_text(text)
    return root / relative


def config_of(root: Path) -> dict[str, Any]:
    return json.loads((root / NEW_CONFIG).read_text())


def test_the_grill_choice_moves_from_preferences_json_into_the_project_config_once(
    tmp_path: Path,
) -> None:
    write(tmp_path, NEW_PREFS, '{"grill": "page"}')
    write(tmp_path, NEW_CONFIG, '{"branch": "x-{issue}"}')

    line = move_grill_preference(tmp_path)

    assert config_of(tmp_path) == {"branch": "x-{issue}", "grill": "page"}
    assert not (tmp_path / NEW_PREFS).exists()
    assert line is not None
    assert NEW_PREFS.as_posix() in line
    assert NEW_CONFIG.as_posix() in line
    assert move_grill_preference(tmp_path) is None


def test_the_move_creates_the_config_and_makes_git_ignore_it(tmp_path: Path) -> None:
    write(tmp_path, NEW_PREFS, '{"grill": "chat"}')

    move_grill_preference(tmp_path)

    assert config_of(tmp_path) == {"grill": "chat"}
    ignore = tmp_path / ".plan-review" / ".gitignore"
    assert ignore.read_text() == "config.json\n.gitignore\n"


def test_a_config_that_already_sets_grill_only_deletes_preferences_json(tmp_path: Path) -> None:
    write(tmp_path, NEW_PREFS, '{"grill": "page"}')
    config = write(tmp_path, NEW_CONFIG, '{"grill": "chat"}')

    line = move_grill_preference(tmp_path)

    assert config.read_text() == '{"grill": "chat"}'
    assert not (tmp_path / NEW_PREFS).exists()
    assert line is not None
    assert "already sets grill" in line


def test_with_no_preferences_json_nothing_moves(tmp_path: Path) -> None:
    assert move_grill_preference(tmp_path) is None
    assert list(tmp_path.iterdir()) == []


def test_a_preferences_json_with_no_choice_is_deleted_and_says_so(tmp_path: Path) -> None:
    write(tmp_path, NEW_PREFS, "{}")
    config = write(tmp_path, NEW_CONFIG, '{"branch": "x-{issue}"}')

    line = move_grill_preference(tmp_path)

    assert not (tmp_path / NEW_PREFS).exists()
    assert config.read_text() == '{"branch": "x-{issue}"}'
    assert line is not None
    assert "no grill choice" in line


@pytest.mark.parametrize("text", ["{bad", '{"grill": "pagex"}'])
def test_an_unreadable_preferences_json_is_left_alone_with_a_line(
    tmp_path: Path, text: str
) -> None:
    prefs = write(tmp_path, NEW_PREFS, text)
    config = write(tmp_path, NEW_CONFIG, "{}")

    line = move_grill_preference(tmp_path)

    assert prefs.read_text() == text
    assert config.read_text() == "{}"
    assert line is not None
    assert "ignored" in line
    assert "delete" in line


def test_the_old_claude_preferences_are_copied_and_never_changed(tmp_path: Path) -> None:
    old = write(tmp_path, OLD_PREFS, '{"grill": "chat"}')

    line = move_grill_preference(tmp_path)

    assert config_of(tmp_path) == {"grill": "chat"}
    assert old.read_bytes() == b'{"grill": "chat"}'
    assert line is not None
    assert OLD_PREFS.as_posix() in line
    assert "copied the grill choice" in line
    assert move_grill_preference(tmp_path) is None


def test_an_old_pipeline_json_keeps_its_settings_when_the_choice_moves(tmp_path: Path) -> None:
    write(tmp_path, OLD_CONFIG, '{"branch": "old-{issue}"}')
    write(tmp_path, NEW_PREFS, '{"grill": "page"}')

    move_grill_preference(tmp_path)

    assert config_of(tmp_path) == {"branch": "old-{issue}", "grill": "page"}


def test_a_broken_project_config_is_left_for_the_reader_to_report(tmp_path: Path) -> None:
    prefs = write(tmp_path, NEW_PREFS, '{"grill": "page"}')
    config = write(tmp_path, NEW_CONFIG, "{bad")

    assert move_grill_preference(tmp_path) is None

    assert prefs.exists()
    assert config.read_text() == "{bad"


def test_old_preferences_with_no_choice_are_left_untouched_and_say_nothing(
    tmp_path: Path,
) -> None:
    old = write(tmp_path, OLD_PREFS, "{}")

    assert move_grill_preference(tmp_path) is None
    assert old.read_bytes() == b"{}"


def test_when_both_preferences_files_exist_the_new_one_is_moved_and_the_old_left_alone(
    tmp_path: Path,
) -> None:
    new = write(tmp_path, NEW_PREFS, '{"grill": "page"}')
    old = write(tmp_path, OLD_PREFS, '{"grill": "chat"}')

    move_grill_preference(tmp_path)

    assert json.loads((tmp_path / NEW_CONFIG).read_text())["grill"] == "page"
    assert not new.exists()
    assert old.read_text() == '{"grill": "chat"}'


@pytest.mark.parametrize("text", ["[]", '"page"'])
def test_a_preferences_json_that_is_not_an_object_is_left_alone_with_a_line(
    tmp_path: Path, text: str
) -> None:
    prefs = write(tmp_path, NEW_PREFS, text)

    line = move_grill_preference(tmp_path)

    assert prefs.read_text() == text
    assert line is not None
    assert "ignored" in line
