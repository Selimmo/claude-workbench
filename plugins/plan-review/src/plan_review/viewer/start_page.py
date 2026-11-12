"""Which page the viewer opens on."""

from plan_review.paths.run_paths import RunPaths
from plan_review.plan.plan_file import PlanFileError, load_plan


def start_page(paths: RunPaths) -> str:
    """The page's path: "" for the plan, "grill" before there is a plan but a grill.

    Raises the PlanFileError from loading the plan when there is nothing to show: a missing
    plan with no grill, or an invalid plan (even next to a grill)."""
    try:
        load_plan(paths.plan)
    except PlanFileError as error:
        if error.missing and paths.grill.is_file():
            return "grill"
        raise
    return ""
