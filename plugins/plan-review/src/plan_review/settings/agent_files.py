"""Finds the agent files a tool looks in, for the project and for the user."""

from collections.abc import Mapping
from pathlib import Path

from plan_review.settings.agent_rules import AgentRules


class AgentFiles:
    def __init__(self, root: Path, rules: Mapping[str, AgentRules]) -> None:
        self._root = root
        self._rules = rules

    def _folders(self, harness: str) -> tuple[list[Path], list[Path]]:
        rules = self._rules[harness]
        project = [self._root / folder for folder in rules.project_agent_folders]
        return project, list(rules.user_agent_folders())

    def both(self, harness: str, name: str) -> tuple[Path | None, Path | None]:
        """The agent file `name` in the project's folders, and in the user's: the first of each."""
        suffix = self._rules[harness].agent_suffix

        def first(folders: list[Path]) -> Path | None:
            found = (folder / f"{name}{suffix}" for folder in folders)
            return next((path for path in found if path.is_file()), None)

        project, user = self._folders(harness)
        return first(project), first(user)

    def find(self, harness: str, name: str) -> Path | None:
        project, user = self.both(harness, name)
        return project or user

    def looked_in(self, harness: str, name: str) -> str:
        suffix = self._rules[harness].agent_suffix
        project, user = self._folders(harness)
        return " and ".join((folder / f"{name}{suffix}").as_posix() for folder in [*project, *user])
