"""Looks for problems in a tool's section, and for warnings the owner should see."""

from collections.abc import Mapping
from pathlib import Path

from plan_review.settings.agent_files import AgentFiles
from plan_review.settings.harness_view import HarnessView
from plan_review.settings.pipeline_config import ModelChoice
from plan_review.settings.steps import FIXED_STEPS, OPTIONAL_AGENTS, REQUIRED_AGENTS, step_problems


def problems(
    view: HarnessView, files: AgentFiles, harness: str, recorded: Mapping[str, str]
) -> list[str]:
    """Everything wrong with one tool's section, one clear line each, naming the file."""
    where = f"harness.{harness}"
    section = view.section(harness)
    found = [
        _from(recorded, f"{where}.workflow", line)
        for line in step_problems(f"{where}.workflow", view.workflow(harness))
    ]
    run = view.names_run(harness)
    builtin = (*REQUIRED_AGENTS, *OPTIONAL_AGENTS, *FIXED_STEPS)
    for name in run:
        if name not in builtin and files.find(harness, name) is None:
            line = (
                f"{where}.workflow: unknown agent {name}: no file found, looked in "
                f"{files.looked_in(harness, name)}"
            )
            found.append(_from(recorded, f"{where}.workflow", line))
    known = {*REQUIRED_AGENTS, *OPTIONAL_AGENTS, *run, *view.config.agents}
    for name, choice in (section.model_extra or {}).items():
        if name in known:
            for field, line in _choice_problems(view, harness, f"{where}.{name}", name, choice):
                found.append(_from(recorded, f"{where}.{name}.{field}", line))
        else:
            found.append(
                _from(recorded, f"{where}.{name}", f"{where}.{name}: unknown agent {name}")
            )
    for role in section.replace or []:
        for line in _replace_problems(files, harness, f"{where}.replace", role):
            found.append(_from(recorded, f"{where}.replace", line))
    return found


def _from(recorded: Mapping[str, str], key: str, line: str) -> str:
    """The line, with the file the setting came from when there is one."""
    source = recorded.get(key)
    if source is None:
        source = next((v for k, v in recorded.items() if k.startswith(f"{key}.")), None)
    return line if source is None else f"{line} (from {source})"


def _choice_problems(
    view: HarnessView, harness: str, where: str, name: str, choice: ModelChoice
) -> list[tuple[str, str]]:
    """Each problem as the setting it is about (`model` or `effort`) and its line."""
    rules = view.rules[harness]
    found: list[tuple[str, str]] = []
    for field, value, allowed in (
        ("model", choice.model, rules.models),
        ("effort", choice.effort, rules.efforts),
    ):
        if value is not None and allowed is not None and value not in allowed:
            line = f"{where}.{field}: '{value}' is not one of {', '.join(sorted(allowed))}"
            found.append((field, line))
    needs_model = rules.effort_needs_model and choice.effort is not None
    if needs_model and view.choice(harness, name).model is None:
        found.append(("effort", f"{where}.effort: needs a model here: set {where}.model too"))
    return found


def _replace_problems(files: AgentFiles, harness: str, where: str, role: str) -> list[str]:
    if role in REQUIRED_AGENTS:
        return [f"{where}: {role} is always plan-review's own; it can't be replaced"]
    if role not in OPTIONAL_AGENTS:
        return [f"{where}: {role} can't be replaced: only {', '.join(OPTIONAL_AGENTS)} can be"]
    if files.find(harness, role) is None:
        return [
            f"{where}: {role} is listed but there is no file for it, looked in "
            f"{files.looked_in(harness, role)}"
        ]
    return []


def warnings(view: HarnessView, files: AgentFiles, harness: str) -> list[str]:
    """One-line notices for the owner."""
    rules = view.rules[harness]
    listed = view.section(harness).replace or []
    lines: list[str] = []
    for role in OPTIONAL_AGENTS:
        project, _ = files.both(harness, role)
        file = files.find(harness, role)
        if file is not None and role in listed:
            lines.append(f"{role}: using {file.as_posix()}")
            if role not in view.names_run(harness):
                lines.append(f"{role} is in replace but the workflow doesn't run it")
            if _file_wins(view, harness, role, file):
                lines.append(
                    f"{role}: {file.as_posix()} sets its own model, which wins over the config's"
                )
        elif project is not None:
            lines.append(
                f'{role}: {project.as_posix()} is not used; to use it, add "replace": '
                f'["{role}"] under harness.{harness} in .plan-review/config.json'
            )
    lines.extend(_custom_file_wins(view, files, harness))
    for role in REQUIRED_AGENTS:
        for name in (role, f"{rules.own_prefix}{role}"):
            project, _ = files.both(harness, name)
            if project is not None:
                lines.append(
                    f"{role}: {project.as_posix()} is not used: plan-review's own {role} "
                    "always runs"
                )
    if not rules.runs_together and any(isinstance(i, list) for i in view.workflow(harness)):
        lines.append(
            f"{harness} can't start agents at the same time: each group runs one after another"
        )
    return lines


def _file_wins(view: HarnessView, harness: str, role: str, file: Path) -> bool:
    sets_model = view.rules[harness].file_sets_model
    chosen = view.chosen(harness, role)
    configured = chosen.model is not None or chosen.effort is not None
    return sets_model is not None and configured and sets_model(file)


def _custom_file_wins(view: HarnessView, files: AgentFiles, harness: str) -> list[str]:
    """Notices for the workflow's own custom agents whose file sets a model."""
    lines: list[str] = []
    for name in view.names_run(harness):
        if name in (*REQUIRED_AGENTS, *OPTIONAL_AGENTS, *FIXED_STEPS):
            continue
        file = files.find(harness, name)
        if file is not None and _file_wins(view, harness, name, file):
            lines.append(
                f"{name}: {file.as_posix()} sets its own model, which wins over the config's"
            )
    return lines
