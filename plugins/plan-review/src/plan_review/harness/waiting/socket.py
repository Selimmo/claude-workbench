"""Waiting through the viewer's WebSocket, with a listener the agent's tool provides."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SocketWaiting:
    """`listener` is the name of the agent tool that subscribes to the socket."""

    listener: str

    start_viewer = (
        "Start `plan-review serve ID` with the Bash tool in the background (`run_in_background`)."
    )
    start_viewer_inline = (
        "start `plan-review serve ID` with the Bash tool in the background (`run_in_background`)"
    )
    resume_viewer = "start `plan-review serve ID` as in point 2"
    ignore_repeat = "ignore it."
    viewer_output = (
        "Read its first output line, `plan-review: <label> at http://127.0.0.1:<port>/`, "
        "from the task's output file, and give the owner that URL."
    )

    @property
    def viewer_kept(self) -> str:
        return (
            f"do not start another (point 1) or arm a second {self.listener} (point 2): "
            f"the same {self.listener} receives the review events too."
        )

    @property
    def keep_viewer(self) -> str:
        return f"Keep the server and the {self.listener} running: step 3 reuses them."

    @property
    def stop_viewer(self) -> str:
        return f"stop the {self.listener} and the server task"

    @property
    def abort_viewer(self) -> str:
        return f"stop the {self.listener} and the server"

    @property
    def grill_listen(self) -> str:
        return (
            f"Subscribe with the **{self.listener}** tool's WebSocket source: "
            "`ws://127.0.0.1:<port>/events`, `timeout_ms: 1800000`, description "
            "`plan-review <label> grill`. When it expires, arm it again and catch up with "
            "`plan-review grill pending ID`, because events sent while no "
            f"{self.listener} listens are lost: handle every pending owner action as below."
        )

    @property
    def review_listen(self) -> str:
        return (
            "Subscribe to the owner's actions with the "
            f"**{self.listener}** tool's WebSocket source: "
            "`ws://127.0.0.1:<port>/events`, `timeout_ms: 1800000`, description "
            f"`plan-review <label>`. A {self.listener} lasts at most 30 minutes: when it "
            "expires before `approved`, arm it again. Events sent while no "
            f"{self.listener} is listening are not replayed "
            "(the viewer keeps the last one only so the owner can press Resend), so each time you "
            "arm it again, catch up: run `plan-review threads ID` and treat every thread whose "
            "last message is the owner's (no reply from you yet) as part of a review, and handle "
            "it as below; if `W/approved.json` exists, the plan was approved: handle it as "
            "`approved` below."
        )
