"""What a tool tells the config reader about its agents."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from plan_review.settings.pipeline_config import ModelChoice


@dataclass(frozen=True)
class AgentRules:
    own_prefix: str  # how plan-review's own agents are named in this tool
    defaults: Mapping[str, ModelChoice]  # each built-in agent's model and effort when none is set
    models: frozenset[str] | None  # the model names the tool takes; None: any
    efforts: frozenset[str] | None
    project_agent_folders: tuple[PurePosixPath, ...]
    user_agent_folders: Callable[[], tuple[Path, ...]]
    agent_suffix: str  # `.md` or `.toml`
    own_agent_file: Callable[[str], Path]  # where plan-review's own instructions for a role are
    effort_needs_model: bool = False  # effort can only be passed together with a model
    runs_together: bool = True  # False: a group runs one after another
    # For a tool where an agent file's own model wins over the one passed at start.
    file_sets_model: Callable[[Path], bool] | None = None
