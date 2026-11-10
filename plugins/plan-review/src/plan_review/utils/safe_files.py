"""Saving files safely: an OS lock for read-modify-write, and writes no reader sees half done."""

import os
import stat
import tempfile
import threading
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from filelock import FileLock


@contextmanager
def file_lock(path: Path, timeout: float = -1) -> Generator[None]:
    """Hold an exclusive lock for a read-modify-write of `path`.

    The server's request threads and the CLI (another process) write the same files, so
    the lock is the OS's (a file lock on a sibling `.lock` file, through the filelock
    package, which works on Windows too), not just a threading.Lock. A `timeout` in seconds
    raises filelock.Timeout when the lock stays busy; by default it waits for as long as it takes.
    """
    with FileLock(path.with_name(f"{path.name}.lock"), timeout=timeout):
        yield


def _umask() -> int:
    mask = os.umask(0)  # reading it means setting it: put it straight back
    os.umask(mask)
    return mask


# Read once, at import: os.umask is process-wide, so not safe to call while threads write.
_NEW_FILE_MODE = 0o666 & ~_umask()


# On Windows a file another handle has open (the server polls these files) cannot be
# replaced: os.replace raises PermissionError until that handle closes.
REPLACE_RETRY_SECONDS = 1.0
_REPLACE_RETRY_PAUSE = 0.01  # between tries, so the wait does not spin a core


def _replace_retrying(src: str, dst: Path) -> None:
    deadline = time.monotonic() + REPLACE_RETRY_SECONDS
    while True:
        try:
            os.replace(src, dst)
        except PermissionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(_REPLACE_RETRY_PAUSE)
        else:
            return


def write_atomically(path: Path, data: bytes) -> None:
    # Write a sibling file then rename: a reader never sees a half-written file. The
    # sibling's name is unique, so two writers never share (and break) one.
    try:
        mode = stat.S_IMODE(path.stat().st_mode)  # keep the file's permissions
    except FileNotFoundError:
        mode = _NEW_FILE_MODE  # as open() would create it (temp files are private)
    # Opened outside `with` so the cleanup below also covers a failed os.replace.
    tmp = tempfile.NamedTemporaryFile(  # noqa: SIM115 - closed by `with tmp` below
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
    )
    try:
        with tmp:
            tmp.write(data)
            tmp.flush()
            os.fchmod(tmp.fileno(), mode)
        _replace_retrying(tmp.name, path)
    except BaseException:
        Path(tmp.name).unlink(missing_ok=True)  # leave no stray temporary file behind
        raise


class HeldLock:
    """The file lock of one store, which may keep it across several calls on one thread.

    An OS file lock can't be taken twice from one thread, so lock() reuses the one that
    this thread took in held(). The mark is per thread: other threads still wait.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._holding = threading.local()

    @contextmanager
    def held(self) -> Generator[None]:
        """Keep the file locked until the block ends, e.g. a whole submit."""
        with file_lock(self._path):
            self._holding.on = True
            try:
                yield
            finally:
                self._holding.on = False

    @contextmanager
    def lock(self) -> Generator[None]:
        """Lock the file for one change, unless this thread already holds it."""
        if getattr(self._holding, "on", False):
            yield
        else:
            with file_lock(self._path):
                yield
