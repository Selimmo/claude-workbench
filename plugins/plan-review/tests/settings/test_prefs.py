"""Saving which way the grill runs into a config file."""

import json
from pathlib import Path

import pytest

from plan_review.settings.pipeline_config import PipelineConfigError
from plan_review.settings.prefs import save_grill_mode


def test_save_grill_mode_sets_grill_and_keeps_the_other_settings(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"branch": "x-{issue}", "checks": [{"name": "a", "run": "a.sh"}]}))

    save_grill_mode(path, "chat")

    assert json.loads(path.read_text()) == {
        "branch": "x-{issue}",
        "checks": [{"name": "a", "run": "a.sh"}],
        "grill": "chat",
    }


def test_save_grill_mode_creates_a_missing_file_and_folder(tmp_path: Path) -> None:
    path = tmp_path / "new" / "folder" / "config.json"

    save_grill_mode(path, "page")

    assert json.loads(path.read_text()) == {"grill": "page"}


@pytest.mark.parametrize("content", [b"{not json", b"[1, 2]"])
def test_save_grill_mode_refuses_a_broken_file_and_writes_nothing(
    tmp_path: Path, content: bytes
) -> None:
    path = tmp_path / "config.json"
    path.write_bytes(content)

    with pytest.raises(PipelineConfigError) as raised:
        save_grill_mode(path, "page")

    assert raised.value.errors[0].startswith(path.as_posix())
    assert path.read_bytes() == content


def test_save_grill_mode_writes_two_space_indented_json_and_a_final_newline(
    tmp_path: Path,
) -> None:
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"branch": "x", "checks": [{"name": "a"}]}))

    save_grill_mode(path, "chat")

    expected = {"branch": "x", "checks": [{"name": "a"}], "grill": "chat"}
    assert path.read_text() == json.dumps(expected, indent=2) + "\n"
