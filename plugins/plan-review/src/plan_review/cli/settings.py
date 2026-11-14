"""`config`, `launch` and `prefs`: the settings in force and the owner's saved choices."""

import json
import sys

from plan_review.cli.runtime import project as project_folder
from plan_review.harness.adapters import all_adapters
from plan_review.paths.workdir import config_file, config_path
from plan_review.settings.migration import move_grill_preference
from plan_review.settings.pipeline_config import PipelineConfig, PipelineConfigError
from plan_review.settings.prefs import GrillMode, save_grill_mode
from plan_review.settings.reader import ConfigReader
from plan_review.settings.user_folder import user_config_dir


def reader() -> ConfigReader:
    """The merged settings: the user's config.json under the project's."""
    return ConfigReader.load(
        project_folder(), user_config_dir(), {h.key: h.rules for h in all_adapters()}
    )


def pipeline_settings() -> tuple[PipelineConfig, str | None]:
    """The settings in force, and a hint to show when they came from an old file."""
    merged = reader()
    return merged.config, merged.move_hint


def print_hint(line: str | None) -> None:
    if line is not None:
        print(line, file=sys.stderr)


def _scope(harness: str | None) -> list[str]:
    return [harness] if harness is not None else [h.key for h in all_adapters()]


def config(harness: str | None) -> int:
    root = project_folder()
    if config_path(root).is_file():
        config_file(root)  # git ignores the project's own settings
    print_hint(move_grill_preference(root))
    try:
        merged = reader()
        problems = [line for key in _scope(harness) for line in merged.problems(key)]
        if problems:
            raise PipelineConfigError(problems)
    except PipelineConfigError as error:
        print("\n".join(error.errors), file=sys.stderr)
        return 1
    report = {"project": root.resolve().as_posix(), **merged.report(harness)}
    print(json.dumps(report, indent=2))
    for key in _scope(harness):
        for line in merged.warnings(key):
            print(line, file=sys.stderr)
    print_hint(merged.move_hint)
    return 0


def launch(name: str, harness: str) -> int:
    try:
        start = reader().launch(harness, name)
    except PipelineConfigError as error:
        print("\n".join(error.errors), file=sys.stderr)
        return 1
    print(json.dumps(start.to_json(), indent=2))
    return 0


def prefs(setting: str, value: str | None, project: bool) -> int:
    assert setting == "grill"
    if value is not None:
        if value not in ("page", "chat"):
            print(f"plan-review prefs grill: give page or chat, not '{value}'", file=sys.stderr)
            return 2
        mode: GrillMode = "page" if value == "page" else "chat"
        target = config_file(project_folder()) if project else user_config_dir() / "config.json"
        try:
            save_grill_mode(target, mode)
        except PipelineConfigError as error:
            print("\n".join(error.errors), file=sys.stderr)
            return 1
        return 0
    try:
        merged = reader()
    except PipelineConfigError as error:
        print("\n".join(error.errors), file=sys.stderr)
        return 1
    print_hint(merged.move_hint)
    if merged.config.grill is None:
        print(
            "no grill mode chosen: ask the owner, then `plan-review prefs grill <mode>`",
            file=sys.stderr,
        )
        return 3
    print(merged.config.grill)
    return 0
