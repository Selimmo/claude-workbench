"""The owner's own choices, kept per project in `.plan-review/work/preferences.json`."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from plan_review.pipeline import PipelineConfig
from plan_review.threads import write_atomically

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
