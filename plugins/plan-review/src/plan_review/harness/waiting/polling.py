"""Waiting by polling `plan-review wait`, for a tool that can't hold a socket open."""

from dataclasses import dataclass

LISTEN_RULES = (
    'An action is handled once you run `plan-review status ID "<text>"`; until then `wait` '
    "offers the same action again, so nothing is lost if you are interrupted."
)


@dataclass(frozen=True)
class PollingWaiting:
    wait_seconds: int = 240

    start_viewer = (
        "Run `plan-review serve ID --detach`. It starts the viewer as a process of its own, "
        "or finds the one already running, and returns at once."
    )
    start_viewer_inline = "run `plan-review serve ID --detach`, which returns at once"
    resume_viewer = "run `plan-review serve ID --detach`, which returns at once (as in point 2)"
    ignore_repeat = (
        'it is already handled: still run `plan-review status ID "Already handled"`, because '
        "`wait` offers an event again until a status confirms it, and nothing behind it is "
        "reached. Do nothing else with it."
    )
    viewer_output = (
        "Read its first output line, `plan-review: <label> at http://127.0.0.1:<port>/`, "
        "and give the owner that URL."
    )
    viewer_kept = (
        "`plan-review serve ID --detach` in point 1 finds it and starts no second one: "
        "carry on from point 2."
    )
    keep_viewer = "Leave the viewer running: step 3 reuses it."
    stop_viewer = "run `plan-review stop ID`"
    abort_viewer = "run `plan-review stop ID`"

    @property
    def grill_listen(self) -> str:
        return (
            f"Wait for the owner by running `plan-review wait ID --timeout {self.wait_seconds}`. "
            "It prints one JSON line: the oldest action of the owner you have not handled, or "
            f'`{{"type":"timeout"}}` after {self.wait_seconds} seconds with nothing new. '
            f'{LISTEN_RULES} After `{{"type":"timeout"}}`, run `plan-review serve ID --detach` '
            "again (it does nothing while the viewer is up; if it started a new one, give the "
            "owner the new link) and wait again. When you resume, catch up before you wait: run "
            "`plan-review wait ID --timeout 0` and handle each event it prints, with a status "
            "each, until it prints a timeout (events the owner sent while no session was waiting "
            "are offered there, and the status confirms them). Then run "
            "`plan-review grill pending ID` and handle every pending owner action as below."
        )

    @property
    def review_listen(self) -> str:
        return (
            f"Wait for the owner by running `plan-review wait ID --timeout {self.wait_seconds}`. "
            "It prints one JSON line: the oldest action of the owner you have not handled, or "
            f'`{{"type":"timeout"}}` after {self.wait_seconds} seconds with nothing new. '
            f'{LISTEN_RULES} After `{{"type":"timeout"}}`, run `plan-review serve ID --detach` '
            "again: it does nothing while the viewer is up, and when it started a new one (the "
            "owner left the page closed for 2 hours), pass on the new link. Then wait again. A "
            '`review_submitted` event with `"approval_withdrawn": true` means the owner had '
            "approved the plan and then sent a review: handle the comments first, as below, then "
            "tell the owner the approval was withdrawn and ask them to approve again. When you "
            "resume a run, catch up before you wait: run `plan-review wait ID --timeout 0` and "
            "handle each event it prints, with a status each, until it prints a timeout (events "
            "the owner sent while no session was waiting are offered there, and the status "
            "confirms them). Then run `plan-review threads ID` and treat every thread whose last "
            "message is the owner's (no reply from you yet) as part of a review, and handle it as "
            "below; if `W/approved.json` exists, the plan was approved: handle it as `approved` "
            "below."
        )
