"""Reads the user's and the project's config.json and merges them, noting each setting's file."""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from pydantic import ValidationError

from plan_review.settings.agent_rules import AgentRules
from plan_review.settings.migration import config_source
from plan_review.settings.pipeline_config import PipelineConfig, PipelineConfigError
from plan_review.utils.json_files import named_errors

BUILT_IN = "built-in"


@dataclass(frozen=True)
class Merged:
    config: PipelineConfig
    recorded: dict[str, str]  # dotted key -> the file it came from
    move_hint: str | None  # the line about an old config file


def _deep_merge(
    low: dict[str, Any], high: dict[str, Any], source: str, sources: dict[str, str], prefix: str
) -> dict[str, Any]:
    """Objects merge key by key; a list or a plain value from `high` replaces the one in `low`.

    Every leaf taken from `high` is recorded in `sources` under its dotted key."""
    merged = dict(low)
    for key, value in high.items():
        dotted = f"{prefix}{key}"
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(
                merged[key], cast(dict[str, Any], value), source, sources, f"{dotted}."
            )
        else:
            merged[key] = value
            _record(value, dotted, source, sources)
    return merged


def _record(value: Any, dotted: str, source: str, sources: dict[str, str]) -> None:
    if isinstance(value, dict) and value:
        for key, inner in cast(dict[str, Any], value).items():
            _record(inner, f"{dotted}.{key}", source, sources)
    else:
        sources[dotted] = source


def leaves(value: Any, dotted: str = "") -> dict[str, Any]:
    """Every setting as a dotted key with its value."""
    if isinstance(value, dict) and value:
        found: dict[str, Any] = {}
        for key, inner in cast(dict[str, Any], value).items():
            found.update(leaves(inner, f"{dotted}.{key}" if dotted else key))
        return found
    return {dotted: value}


def load_merged(root: Path, user_dir: Path, rules: Mapping[str, AgentRules]) -> Merged:
    """Checks each file on its own, then merges them: project over user over built-in."""
    project = config_source(root)
    errors: list[str] = []
    merged: dict[str, Any] = {}
    recorded: dict[str, str] = {}
    for path in (user_dir / "config.json", project.path):
        if not path.is_file():
            continue
        raw = path.read_text(encoding="utf-8")
        try:
            PipelineConfig.model_validate_json(raw)
        except ValidationError as error:
            errors.extend(named_errors(path, error))
            continue
        data = json.loads(raw)
        for tool in data.get("harness", {}):
            if tool not in rules:
                errors.append(
                    f'{path.as_posix()}: harness.{tool}: unknown harness "{tool}" '
                    f"(known: {', '.join(rules)})"
                )
        merged = _deep_merge(merged, data, path.as_posix(), recorded, "")
    if errors:
        raise PipelineConfigError(errors)
    return Merged(PipelineConfig.model_validate(merged), recorded, project.move_hint)
