"""Old `.claude/` files are read when they are the only ones; nothing is written or moved."""

from pathlib import Path

from plan_review.migration import config_source, preferences_source

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


def test_preferences_source_with_neither_file_is_the_new_path_with_no_hint(
    tmp_path: Path,
) -> None:
    source = preferences_source(tmp_path)

    assert source.path == tmp_path / NEW_PREFS
    assert source.move_hint is None


def test_preferences_source_uses_the_old_file_when_it_is_the_only_one(tmp_path: Path) -> None:
    touch(tmp_path, OLD_PREFS)

    source = preferences_source(tmp_path)

    assert source.path == tmp_path / OLD_PREFS
    assert source.move_hint is not None
    assert "\n" not in source.move_hint
    assert "plan-review prefs grill" in source.move_hint


def test_preferences_source_prefers_the_new_file_when_both_exist(tmp_path: Path) -> None:
    touch(tmp_path, OLD_PREFS)
    touch(tmp_path, NEW_PREFS)

    source = preferences_source(tmp_path)

    assert source.path == tmp_path / NEW_PREFS
    assert source.move_hint is None
