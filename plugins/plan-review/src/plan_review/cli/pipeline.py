"""The steps around a run: init, schema, validate, branch, verdict and tree-hash."""

import json
import sys
from pathlib import Path

from plan_review.cli.runtime import Runtime
from plan_review.cli.settings import pipeline_settings, print_hint
from plan_review.paths.run_id import InvalidRunId, check_run_id, label
from plan_review.paths.run_paths import RunPaths
from plan_review.paths.workdir import new_prompt_work_dir
from plan_review.pipeline import orchestration
from plan_review.pipeline.orchestration import MalformedReview
from plan_review.plan.plan import Plan, PlanFileError, load_plan, record_branch, shape_problems
from plan_review.settings.pipeline_config import PipelineConfigError


def init(run_id: str | None, prompt: str | None, *, runtime: Runtime) -> int:
    if (run_id is None) == (prompt is None):
        print("plan-review init: give either a run id or --prompt <name>", file=sys.stderr)
        return 2
    if prompt is not None:
        today = runtime.today()
        try:
            check_run_id(f"{prompt}-{today.isoformat()}")
        except InvalidRunId as error:
            print(error, file=sys.stderr)
            return 2
        print(new_prompt_work_dir(Path(), prompt, today).as_posix())
        return 0
    assert run_id is not None
    print(runtime.ensure_work_dir(Path(), run_id).as_posix())
    return 0


def schema() -> int:
    print(json.dumps(Plan.model_json_schema(), indent=2))
    return 0


def validate(file: Path) -> int:
    try:
        plan = load_plan(file)
    except PlanFileError as error:
        print("\n".join(error.errors), file=sys.stderr)
        return 2 if error.missing else 1
    problems = shape_problems(plan)
    if problems:
        print("\n".join(f"{file.as_posix()}: {line}" for line in problems), file=sys.stderr)
        return 1
    print(f"OK: plan for {label(plan.issue.id)} ({len(plan.element_ids())} elements)")
    return 0


def branch(run_id: str, *, runtime: Runtime) -> int:
    plan_file = RunPaths(runtime.work_dir(Path(), run_id)).plan
    try:
        plan = load_plan(plan_file)
        if plan.branch:  # already named (and maybe created): never name it again
            print(plan.branch)
            return 0
        config, hint = pipeline_settings()
        pattern = config.branch
    except (PlanFileError, PipelineConfigError) as error:
        print("\n".join(error.errors), file=sys.stderr)
        return 1
    name = orchestration.branch_name(run_id, plan.issue, pattern)
    record_branch(plan_file, name)
    print(name)
    print_hint(hint)
    return 0


def verdict(file: Path) -> int:
    try:
        result = orchestration.verdict(file)
    except MalformedReview as error:
        print(error, file=sys.stderr)
        return 2
    print(result)
    return 0 if result == "PASS" else 1


def tree_hash() -> int:
    print(orchestration.tree_hash(Path.cwd()))
    return 0
