"""One tool's section of the merged config, with the built-in defaults filled in."""

from collections.abc import Mapping

from plan_review.settings.agent_rules import AgentRules
from plan_review.settings.pipeline_config import HarnessSection, ModelChoice, PipelineConfig
from plan_review.settings.steps import BUILT_IN_WORKFLOW


def as_group(item: str | list[str]) -> list[str]:
    return [item] if isinstance(item, str) else item


class HarnessView:
    def __init__(self, config: PipelineConfig, rules: Mapping[str, AgentRules]) -> None:
        self.config = config
        self.rules = rules

    def section(self, harness: str) -> HarnessSection:
        return self.config.harness.get(harness) or HarnessSection()

    def workflow(self, harness: str) -> list[str | list[str]]:
        workflow = self.section(harness).workflow
        return list(BUILT_IN_WORKFLOW) if workflow is None else workflow

    def names_run(self, harness: str) -> list[str]:
        return [name for item in self.workflow(harness) for name in as_group(item)]

    def chosen(self, harness: str, name: str) -> ModelChoice:
        return (self.section(harness).model_extra or {}).get(name) or ModelChoice()

    def choice(self, harness: str, name: str) -> ModelChoice:
        """The model and effort in force: the config's, else the tool's default, else none."""
        default = self.rules[harness].defaults.get(name) or ModelChoice()
        chosen = self.chosen(harness, name)
        return ModelChoice(
            model=chosen.model if chosen.model is not None else default.model,
            effort=chosen.effort if chosen.effort is not None else default.effort,
        )
