"""A skill file plus agents as TOML, all inside one folder and carrying a mark."""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath

from plan_review.harness.workflow import Workflow, fill


def toml_multiline(text: str) -> str:
    """`text` as a TOML multi-line basic string that reads back exactly."""
    body = text.replace("\\", "\\\\").replace('"""', '""\\"').replace("\r", "\\r")
    return f'"""\n{body}"""'


@dataclass(frozen=True)
class TomlAgents:
    """`folder` is where the files go, `mark` goes in every one of them, and `extra_files`
    are written as given, inside `folder`."""

    folder: PurePosixPath
    mark: str
    extra_files: Mapping[PurePosixPath, str]

    def _agent_toml(self, name: str, description: str, instructions: str) -> str:
        return (
            f"# {self.mark}: edit workflow/, not this file\n"
            f"name = {json.dumps(name)}\n"
            f"description = {json.dumps(description)}\n"
            f"developer_instructions = {toml_multiline(instructions)}\n"
        )

    def files(self, workflow: Workflow, slots: Mapping[str, str]) -> dict[PurePosixPath, str]:
        ship = workflow.ship
        skill = (
            f"---\nname: {ship.name}\ndescription: {ship.description}\n---\n\n"
            f"<!-- {self.mark}: edit workflow/, not this file -->\n" + fill(ship.body, slots)
        )
        files = {self.folder / "skills/ship/SKILL.md": skill}
        files.update({self.folder / path: text for path, text in self.extra_files.items()})
        for name, agent in workflow.agents.items():
            agent_name = f"{slots['agent_prefix']}{name}"
            files[self.folder / f"agents/{agent_name}.toml"] = self._agent_toml(
                agent_name, agent.description, fill(agent.body, slots)
            )
        return files
