"""A tool's own names for things: the words the workflow leaves to it."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Wording:
    """Every field is required, so a missing fill-in fails when the tool's file is imported."""

    arguments: str
    agent_prefix: str
    agent_override: str
    rules_file: str
    rules_also: str
    harness_folder: str
    skill_tool: str
