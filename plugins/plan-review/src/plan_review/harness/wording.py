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
    start_agent: str  # how to start one agent with the `launch` values, in the tool's words
    start_together: str  # how to start a group at once and wait for every result
    unknown_agent: str  # what to do when the tool says an agent doesn't exist
