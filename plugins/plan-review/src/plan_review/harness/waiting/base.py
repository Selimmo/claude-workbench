"""How an agent waits for the owner: the texts the workflow leaves to it."""

from typing import Protocol

# The workflow's {{slot}} names that a WaitingStyle fills in.
WAITING_TEXTS = (
    "start_viewer",
    "start_viewer_inline",
    "resume_viewer",
    "ignore_repeat",
    "viewer_output",
    "viewer_kept",
    "keep_viewer",
    "stop_viewer",
    "abort_viewer",
    "grill_listen",
    "review_listen",
)


class WaitingStyle(Protocol):
    @property
    def start_viewer(self) -> str: ...
    @property
    def start_viewer_inline(self) -> str: ...
    @property
    def resume_viewer(self) -> str: ...
    @property
    def ignore_repeat(self) -> str: ...
    @property
    def viewer_output(self) -> str: ...
    @property
    def viewer_kept(self) -> str: ...
    @property
    def keep_viewer(self) -> str: ...
    @property
    def stop_viewer(self) -> str: ...
    @property
    def abort_viewer(self) -> str: ...
    @property
    def grill_listen(self) -> str: ...
    @property
    def review_listen(self) -> str: ...
