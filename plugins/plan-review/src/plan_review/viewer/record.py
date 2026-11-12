"""viewer.json: the one owner of the file that says where a run's detached viewer is."""

import json
from contextlib import AbstractContextManager
from pathlib import Path

from pydantic import BaseModel, TypeAdapter

from plan_review.paths.run_paths import RunPaths
from plan_review.utils.json_files import read_file
from plan_review.utils.safe_files import file_lock, write_atomically


class ViewerInfo(BaseModel):
    """What viewer.json holds: which process and port a run's viewer has, and the stop token."""

    run_id: str
    pid: int
    port: int
    token: str


_Info = TypeAdapter(ViewerInfo)


class ViewerRecord:
    """Reads, writes and removes a run's viewer.json. Nothing else touches that file."""

    def __init__(self, work: Path) -> None:
        self._file = RunPaths(work).viewer

    def read(self) -> ViewerInfo | None:
        """None when there is no file; BrokenFile when it doesn't parse."""
        return read_file(self._file, _Info)

    def write(self, info: ViewerInfo) -> None:
        write_atomically(self._file, _Info.dump_json(info, indent=2))

    def remove_if_mine(self, token: str) -> None:
        """Remove the file if it is still this viewer's (a newer viewer's is left alone).

        A missing or unreadable file counts as not newer. Callers hold `locked()`.
        """
        try:
            held = json.loads(self._file.read_text()).get("token")
        except OSError, ValueError, AttributeError:
            held = None
        if held in (None, token):
            self._file.unlink(missing_ok=True)

    def locked(self, timeout: float = -1) -> AbstractContextManager[None]:
        """viewer.json's lock: whoever holds it starts or stops a viewer.

        A `timeout` in seconds raises filelock.Timeout when the lock stays busy.
        """
        return file_lock(self._file, timeout=timeout)
