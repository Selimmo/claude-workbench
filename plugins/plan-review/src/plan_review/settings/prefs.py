"""The owner's own choice of how the grill runs, kept in a config file."""

import json
from pathlib import Path
from typing import Any, Literal, cast

from plan_review.settings.pipeline_config import PipelineConfigError
from plan_review.utils.safe_files import write_atomically

GrillMode = Literal["page", "chat"]


def save_grill_mode(path: Path, mode: GrillMode) -> None:
    """Set `grill` in the config file at `path`, keeping every other setting.

    Creates the file and folder if needed. A file that isn't JSON raises PipelineConfigError
    and nothing is written."""
    loaded: Any = {}
    if path.is_file():
        try:
            loaded = json.loads(path.read_bytes())
        except ValueError as error:
            raise PipelineConfigError([f"{path.as_posix()}: not valid JSON: {error}"]) from error
    if not isinstance(loaded, dict):
        raise PipelineConfigError([f"{path.as_posix()}: must hold a JSON object"])
    settings = cast(dict[str, Any], loaded)
    settings["grill"] = mode
    path.parent.mkdir(parents=True, exist_ok=True)
    write_atomically(path, (json.dumps(settings, indent=2) + "\n").encode())
