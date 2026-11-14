"""The one front door to the user's and the project's config.json."""

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal, Self

from plan_review.settings import checks
from plan_review.settings.agent_files import AgentFiles
from plan_review.settings.agent_rules import AgentRules
from plan_review.settings.config_merge import BUILT_IN, Merged, leaves, load_merged
from plan_review.settings.harness_view import HarnessView
from plan_review.settings.pipeline_config import PipelineConfig, PipelineConfigError
from plan_review.settings.steps import (
    OPTIONAL_AGENTS,
    REQUIRED_AGENTS,
    AgentStart,
    review_file,
)

_KINDS: dict[str, Literal["grill-explorer", "architect", "implementer", "reviewer"]] = {
    "grill-explorer": "grill-explorer",
    "architect": "architect",
    "implementer": "implementer",
}


class ConfigReader:
    def __init__(
        self,
        root: Path,
        config: PipelineConfig,
        recorded: dict[str, str],
        rules: Mapping[str, AgentRules],
        move_hint: str | None,
    ) -> None:
        self.config = config
        self.move_hint = move_hint  # the line about an old config file
        self._recorded = recorded
        self._rules = rules
        self._view = HarnessView(config, rules)
        self._files = AgentFiles(root, rules)

    @classmethod
    def load(cls, root: Path, user_dir: Path, rules: Mapping[str, AgentRules]) -> Self:
        """Checks each file on its own, then merges them: project over user over built-in."""
        merged: Merged = load_merged(root, user_dir, rules)
        return cls(root, merged.config, merged.recorded, rules, merged.move_hint)

    def settings(self, harness: str | None = None) -> dict[str, Any]:
        """The merged settings, with each tool's resolved workflow and agents' model and effort.

        With a `harness`, only that tool's section."""
        settings = self.config.model_dump(mode="json")
        tools = list(self._rules) if harness is None else [harness]
        settings["harness"] = {tool: self._resolved(tool) for tool in tools}
        return settings

    def _resolved(self, harness: str) -> dict[str, Any]:
        section: dict[str, Any] = {
            "workflow": self._view.workflow(harness),
            "replace": self._view.section(harness).replace or [],
        }
        names = [
            *REQUIRED_AGENTS,
            *OPTIONAL_AGENTS,
            *(n for n in self._view.names_run(harness) if n not in OPTIONAL_AGENTS),
        ]
        for name in names:
            choice = self._view.choice(harness, name)
            section[name] = {"model": choice.model, "effort": choice.effort}
        return section

    def sources(self, harness: str | None = None) -> dict[str, str]:
        """Each setting in force, as a dotted key, with the file it came from or `built-in`."""
        return {key: self._recorded.get(key, BUILT_IN) for key in leaves(self.settings(harness))}

    def report(self, harness: str | None = None) -> dict[str, Any]:
        """What `plan-review config` prints."""
        return {"settings": self.settings(harness), "from": self.sources(harness)}

    def problems(self, harness: str) -> list[str]:
        """Everything wrong with one tool's section, one clear line each."""
        return checks.problems(self._view, self._files, harness, self._recorded)

    def warnings(self, harness: str) -> list[str]:
        """One-line notices for the owner."""
        return checks.warnings(self._view, self._files, harness)

    def _check(self, harness: str) -> None:
        found = self.problems(harness)
        if found:
            raise PipelineConfigError(found)

    def _replaced(self, harness: str) -> list[str]:
        """The optional roles that run from your own file: listed in `replace` and found."""
        listed = self._view.section(harness).replace or []
        return [
            role
            for role in OPTIONAL_AGENTS
            if role in listed and self._files.find(harness, role) is not None
        ]

    def launch(self, harness: str, name: str) -> AgentStart:
        """How to start one agent now."""
        self._check(harness)
        rules = self._rules[harness]
        if name not in REQUIRED_AGENTS and name not in self._view.names_run(harness):
            if name == "implementer":
                return AgentStart(
                    name=name,
                    kind="implementer",
                    agent=None,
                    model=None,
                    effort=None,
                    main_session=True,
                    instructions=rules.own_agent_file(name).as_posix(),
                )
            raise PipelineConfigError([f"{name} is not in the workflow of {harness}"])
        choice = self._view.choice(harness, name)
        own = name in (*REQUIRED_AGENTS, *OPTIONAL_AGENTS)
        replaced = name in self._replaced(harness)
        kind = _KINDS.get(name, "reviewer")
        return AgentStart(
            name=name,
            kind=kind,
            agent=f"{rules.own_prefix}{name}" if own and not replaced else name,
            model=choice.model,
            effort=choice.effort,
            review=review_file(name) if kind == "reviewer" else None,
        )
