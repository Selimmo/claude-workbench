"""`config` and `prefs`: the project's settings and the owner's saved choices."""

import sys
from pathlib import Path

from plan_review.paths.workdir import preferences_file
from plan_review.settings.migration import config_source
from plan_review.settings.pipeline_config import PipelineConfig, PipelineConfigError, load_pipeline
from plan_review.settings.prefs import GrillMode, PreferencesError, chosen_grill_mode, record


def pipeline_settings() -> tuple[PipelineConfig, str | None]:
    """The project's settings, and a hint to show when they came from an old file."""
    source = config_source(Path())
    return load_pipeline(source.path), source.move_hint


def print_hint(line: str | None) -> None:
    if line is not None:
        print(line, file=sys.stderr)


def config() -> int:
    try:
        settings, hint = pipeline_settings()
    except PipelineConfigError as error:
        print("\n".join(error.errors), file=sys.stderr)
        return 1
    print(settings.model_dump_json(indent=2))
    print_hint(hint)
    return 0


def prefs(setting: str, value: str | None) -> int:
    assert setting == "grill"
    if value is not None:
        if value not in ("page", "chat"):
            print(f"plan-review prefs grill: give page or chat, not '{value}'", file=sys.stderr)
            return 2
        mode: GrillMode = "page" if value == "page" else "chat"
        record(preferences_file(Path()), mode)
        return 0
    try:
        choice = chosen_grill_mode(Path())
    except (PipelineConfigError, PreferencesError) as error:
        print("\n".join(error.errors), file=sys.stderr)
        return 1
    for hint in choice.hints:
        print_hint(hint)
    if choice.mode is None:
        print(
            "no grill mode chosen: ask the owner, then `plan-review prefs grill <mode>`",
            file=sys.stderr,
        )
        return 3
    print(choice.mode)
    return 0
