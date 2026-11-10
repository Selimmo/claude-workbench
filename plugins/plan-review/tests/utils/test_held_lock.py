"""HeldLock: keep a file locked across several calls on one thread."""

import threading
from pathlib import Path

import pytest
from filelock import Timeout

from plan_review.utils import HeldLock, file_lock


def test_held_keeps_the_file_locked_until_the_block_ends(tmp_path: Path) -> None:
    path = tmp_path / "drafts.json"
    held = HeldLock(path)

    with held.held(), pytest.raises(Timeout), file_lock(path, timeout=0.05):
        pass

    with file_lock(path, timeout=0.05):  # the block ended: free at once
        pass


def test_lock_inside_held_on_the_same_thread_does_not_wait(tmp_path: Path) -> None:
    path = tmp_path / "drafts.json"
    held = HeldLock(path)

    with held.held():
        with held.lock():
            pass
        with pytest.raises(Timeout), file_lock(path, timeout=0.05):  # the inner block kept it
            pass


def assert_mark_cleared(held: HeldLock, path: Path) -> None:
    """On this thread, lock() must take the real OS lock again."""
    with held.lock(), pytest.raises(Timeout), file_lock(path, timeout=0.05):
        pass


def test_the_mark_is_cleared_when_held_ends(tmp_path: Path) -> None:
    path = tmp_path / "drafts.json"
    held = HeldLock(path)

    with held.held():
        pass

    assert_mark_cleared(held, path)


def test_the_mark_is_cleared_when_the_held_block_raises(tmp_path: Path) -> None:
    path = tmp_path / "drafts.json"
    held = HeldLock(path)

    with pytest.raises(RuntimeError), held.held():
        raise RuntimeError

    assert_mark_cleared(held, path)


def test_another_thread_lock_waits_while_one_thread_holds(tmp_path: Path) -> None:
    held = HeldLock(tmp_path / "drafts.json")
    inside = threading.Event()
    ready = threading.Event()

    def other() -> None:
        ready.set()
        with held.lock():
            inside.set()

    thread = threading.Thread(target=other)
    with held.held():
        thread.start()
        assert ready.wait(5)
        assert not inside.wait(0.1)
    assert inside.wait(5)
    thread.join()
