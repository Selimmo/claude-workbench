"""The grill's commands: post, pending, decisions and schema."""

import json
import sys
from collections.abc import Callable
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from plan_review.cli.runtime import Runtime, project
from plan_review.grill.decisions_md import decisions_markdown
from plan_review.grill.drafts import GrillDraftStore
from plan_review.grill.state import GrillError, SubmittedAnswer
from plan_review.grill.store import GrillStore, post_turn
from plan_review.grill.turn import Turn
from plan_review.paths.run_id import label
from plan_review.paths.run_paths import RunPaths
from plan_review.utils.json_files import named_errors

_ANSWERS = TypeAdapter(list[SubmittedAnswer])


def schema() -> int:
    print(json.dumps(Turn.model_json_schema(), indent=2))
    return 0


def post(run_id: str, file: Path, *, runtime: Runtime) -> int:
    if not file.is_file():
        print(f"{file.as_posix()}: file not found", file=sys.stderr)
        return 2
    paths = RunPaths(runtime.ensure_work_dir(project(), run_id))
    try:
        posted = post_turn(
            GrillStore(paths.grill), GrillDraftStore(paths.grill_drafts), file.read_bytes()
        )
    except GrillError as error:
        print("\n".join(error.errors), file=sys.stderr)
        return 1
    if posted.drafts_problem is not None:
        print(posted.drafts_problem, file=sys.stderr)  # the turn is posted; the page reports this
    state = posted.state
    print(f"posted: {len(state.rounds)} rounds, {len(state.open_questions())} questions open")
    return 0


def pending(run_id: str, *, runtime: Runtime) -> int:
    store = GrillStore(RunPaths(runtime.work_dir(project(), run_id)).grill)
    try:
        state = store.get()
    except GrillError as error:
        print("\n".join(error.errors), file=sys.stderr)
        return 1
    result = {"confirmed": state.confirmed_at is not None, "pending": store.pending()}
    print(json.dumps(result, indent=2))
    return 0


def decisions(run_id: str, *, runtime: Runtime) -> int:
    paths = RunPaths(runtime.work_dir(project(), run_id))
    try:
        state = GrillStore(paths.grill).get()
    except GrillError as error:
        print("\n".join(error.errors), file=sys.stderr)
        return 1
    if state.confirmed_at is None:
        print(f"the grill for {label(run_id)} is not confirmed yet", file=sys.stderr)
        return 1
    paths.decisions.write_text(decisions_markdown(state, label(run_id)), encoding="utf-8")
    print(paths.decisions.as_posix())
    return 0


def _record(run_id: str, action: Callable[[GrillStore], object], *, runtime: Runtime) -> int:
    store = GrillStore(RunPaths(runtime.work_dir(project(), run_id)).grill)
    try:
        action(store)
    except GrillError as error:
        print("\n".join(error.errors), file=sys.stderr)
        return 1
    return 0


def answer(run_id: str, file: Path, *, runtime: Runtime) -> int:
    """The owner's answers to the open questions, as the page's submit records them."""
    if not file.is_file():
        print(f"{file.as_posix()}: file not found", file=sys.stderr)
        return 2
    try:
        answers = _ANSWERS.validate_json(file.read_bytes())
    except ValidationError as error:
        print("\n".join(named_errors(file, error)), file=sys.stderr)
        return 1
    return _record(run_id, lambda store: store.submit(answers), runtime=runtime)


def confirm(run_id: str, *, runtime: Runtime) -> int:
    return _record(run_id, lambda store: store.confirm(), runtime=runtime)


def reopen(run_id: str, text: str, *, runtime: Runtime) -> int:
    return _record(run_id, lambda store: store.reopen(text), runtime=runtime)
