"""The owner's own choices, kept per project in `.plan-review/work/preferences.json`."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ValidationError

from plan_review.settings.migration import config_source, preferences_source
from plan_review.settings.pipeline_config import PipelineConfig, load_pipeline
from plan_review.utils.json_files import named_errors
from plan_review.utils.safe_files import write_atomically

GrillMode = Literal["page", "chat"]


class Preferences(BaseModel):
    grill: GrillMode | None = None


def load_preferences(path: Path) -> Preferences:
    if not path.is_file():
        return Preferences()
    return Preferences.model_validate_json(path.read_bytes())


def record(path: Path, grill: GrillMode) -> None:
    write_atomically(path, Preferences(grill=grill).model_dump_json(exclude_none=True).encode())


def grill_mode(config: PipelineConfig, prefs: Preferences) -> GrillMode | None:
    """The team's setting in the config wins over the owner's recorded preference."""
    return config.grill or prefs.grill


class PreferencesError(Exception):
    """A preferences file that can't be read, one named line per problem."""

    def __init__(self, errors: list[str]) -> None:
        super().__init__("\n".join(errors))
        self.errors = errors


@dataclass(frozen=True)
class GrillChoice:
    mode: GrillMode | None  # None: nothing is chosen yet
    hints: tuple[str, ...]  # where old files were read from and how to move them, in order


def chosen_grill_mode(root: Path) -> GrillChoice:
    """The grill mode for the project at `root`: its config first, then the owner's saved choice.

    A broken config raises PipelineConfigError before the preferences are read; a broken
    preferences file raises PreferencesError. Either way no hints are returned."""
    config_file = config_source(root)
    config = load_pipeline(config_file.path)
    preferences_file = preferences_source(root)
    try:
        prefs = load_preferences(preferences_file.path)
    except ValidationError as error:
        raise PreferencesError(named_errors(preferences_file.path, error)) from error
    hints = tuple(h for h in (config_file.move_hint, preferences_file.move_hint) if h is not None)
    return GrillChoice(grill_mode(config, prefs), hints)
