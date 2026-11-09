import os
import stat
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from threading import Event
from threading import Thread as Thread_

import pytest
from conftest import posix_only

from plan_review import threads
from plan_review.file_errors import BrokenFile
from plan_review.threads import Author, ThreadNotFound, ThreadStore


@pytest.fixture
def store(tmp_path: Path) -> ThreadStore:
    return ThreadStore(tmp_path / "comments.json")


def test_new_thread_is_anchored_open_and_starts_with_the_owners_message(
    store: ThreadStore,
) -> None:
    thread = store.create("class:HintPolicy", "Why a class, not a function?")

    assert thread.anchor == "class:HintPolicy"
    assert not thread.resolved
    assert [(m.author, m.text) for m in thread.messages] == [
        ("owner", "Why a class, not a function?")
    ]


def test_threads_persist_so_another_store_on_the_same_file_sees_them(tmp_path: Path) -> None:
    path = tmp_path / "comments.json"
    created = ThreadStore(path).create("test:1", "Add an edge case?")

    assert ThreadStore(path).all() == [created]


def test_reply_appends_a_message_from_the_given_author(store: ThreadStore) -> None:
    thread = store.create("class:HintPolicy", "Why a class?")

    store.reply(thread.id, "It holds max_hints.", author="claude")
    store.reply(thread.id, "OK", author="owner")

    (saved,) = store.all()
    assert [(m.author, m.text) for m in saved.messages][1:] == [
        ("claude", "It holds max_hints."),
        ("owner", "OK"),
    ]


def test_old_comments_with_the_claude_author_still_load(store: ThreadStore, tmp_path: Path) -> None:
    thread = store.create("class:HintPolicy", "Why a class?")
    store.reply(thread.id, "Because.", author="agent")
    path = tmp_path / "comments.json"
    old = path.read_bytes().replace(b'"agent"', b'"claude"')
    path.write_bytes(old)

    (loaded,) = ThreadStore(path).all()

    assert [m.author for m in loaded.messages] == ["owner", "claude"]
    assert path.read_bytes() == old  # reading never rewrites it


def test_resolve_and_reopen_toggle_the_thread(store: ThreadStore) -> None:
    thread = store.create("risk:1", "Agreed")
    store.reply(thread.id, "Noted.", author="agent")

    assert store.set_resolved(thread.id, True).resolved
    assert not store.set_resolved(thread.id, False).resolved
    assert not store.all()[0].resolved


def test_unknown_thread_id_raises_thread_not_found(store: ThreadStore) -> None:
    with pytest.raises(ThreadNotFound, match="t-nope"):
        store.reply("t-nope", "hello", author="claude")


@pytest.mark.parametrize("text", ["", "   \n"])
def test_blank_text_is_refused(store: ThreadStore, text: str) -> None:
    with pytest.raises(ValueError, match="empty"):
        store.create("risk:1", text)
    thread = store.create("risk:1", "real")
    with pytest.raises(ValueError, match="empty"):
        store.reply(thread.id, text, author="owner")


def test_threads_on_elements_missing_from_the_plan_are_orphaned(store: ThreadStore) -> None:
    store.create("class:HintPolicy", "a")
    gone = store.create("class:Removed", "b")
    store.create("tab:risks", "c")

    orphans = store.orphaned(element_ids={"class:HintPolicy"})

    assert [t.id for t in orphans] == [gone.id]


def test_threads_on_the_plan_header_never_orphan(store: ThreadStore) -> None:
    store.create("header:title", "Rename the issue?")
    store.create("header:summary", "Too long")

    assert store.orphaned(element_ids=set()) == []


def test_get_finds_a_thread_by_id(store: ThreadStore) -> None:
    wanted = store.create("risk:1", "a")
    store.create("risk:2", "b")

    assert store.get(wanted.id) == wanted


def test_get_of_an_unknown_id_raises_thread_not_found(store: ThreadStore) -> None:
    store.create("risk:1", "a")

    with pytest.raises(ThreadNotFound):
        store.get("t-nope")


def test_writes_use_their_own_temporary_file(tmp_path: Path) -> None:
    # Another writer's temporary file (here: something in the way at the old fixed name)
    # must not break this write.
    (tmp_path / "comments.tmp").mkdir()
    store = ThreadStore(tmp_path / "comments.json")
    errors: list[OSError] = []

    try:
        store.create("risk:1", "a")
    except OSError as error:
        errors.append(error)

    assert errors == []
    assert [t.anchor for t in store.all()] == ["risk:1"]


def test_concurrent_writers_lose_no_update(tmp_path: Path) -> None:
    path = tmp_path / "comments.json"
    thread = ThreadStore(path).create("risk:1", "start")

    def reply_many(author: Author) -> None:
        store = ThreadStore(path)  # as the server and the CLI each have their own
        for i in range(40):
            store.reply(thread.id, f"{author} {i}", author=author)

    workers = [Thread_(target=reply_many, args=(a,)) for a in ("owner", "claude")]
    for w in workers:
        w.start()
    for w in workers:
        w.join()

    assert len(ThreadStore(path).get(thread.id).messages) == 1 + 2 * 40


def run_together(*jobs: Callable[[], object]) -> None:
    workers = [Thread_(target=job) for job in jobs]
    for w in workers:
        w.start()
    for w in workers:
        w.join()


def test_concurrent_new_threads_are_all_kept(tmp_path: Path) -> None:
    path = tmp_path / "comments.json"

    def create_many(prefix: str) -> None:
        store = ThreadStore(path)
        for i in range(40):
            store.create(f"{prefix}:{i}", "x")

    run_together(lambda: create_many("a"), lambda: create_many("b"))

    assert len(ThreadStore(path).all()) == 80


@posix_only
def test_a_new_file_gets_the_usual_permissions_not_private_ones(tmp_path: Path) -> None:
    umask = os.umask(0)
    os.umask(umask)

    ThreadStore(tmp_path / "comments.json").create("risk:1", "a")

    assert stat.S_IMODE((tmp_path / "comments.json").stat().st_mode) == 0o666 & ~umask


@posix_only
def test_rewriting_a_file_keeps_its_permissions(tmp_path: Path) -> None:
    store = ThreadStore(tmp_path / "comments.json")
    store.create("risk:1", "a")
    (tmp_path / "comments.json").chmod(0o640)

    store.create("risk:2", "b")

    assert stat.S_IMODE((tmp_path / "comments.json").stat().st_mode) == 0o640


def test_a_failed_write_leaves_no_temporary_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(*_: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", fail)

    with pytest.raises(OSError, match="disk full"):
        ThreadStore(tmp_path / "comments.json").create("risk:1", "a")

    assert list(tmp_path.glob("*.tmp")) == []


def test_stores_work_without_fcntl(tmp_path: Path) -> None:
    # Windows has no fcntl: the module must import and write all the same.
    code = (
        "import sys; sys.modules['fcntl'] = None\n"
        "from pathlib import Path\n"
        "from plan_review.threads import ThreadStore\n"
        f"ThreadStore(Path({str(tmp_path / 'comments.json')!r})).create('risk:1', 'a')\n"
    )

    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=False
    )

    assert result.returncode == 0, result.stderr


def refuse_replace_times(
    monkeypatch: pytest.MonkeyPatch, refusals: int | None
) -> list[tuple[object, object]]:
    """os.replace refuses `refusals` times (always, for None) with PermissionError, as
    Windows does while another handle has the target open; then does the real thing."""
    calls: list[tuple[object, object]] = []
    real = os.replace

    def replace(src: str, dst: Path) -> None:
        calls.append((src, dst))
        if refusals is None or len(calls) <= refusals:
            raise PermissionError("in use")
        real(src, dst)

    monkeypatch.setattr(os, "replace", replace)
    return calls


def test_a_replace_refused_while_the_file_is_open_is_retried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = refuse_replace_times(monkeypatch, 2)

    thread = ThreadStore(tmp_path / "comments.json").create("risk:1", "a")

    assert [t.id for t in ThreadStore(tmp_path / "comments.json").all()] == [thread.id]
    assert len(calls) == 3


def test_a_replace_still_refused_after_the_retry_window_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(threads, "REPLACE_RETRY_SECONDS", 0.1)
    calls = refuse_replace_times(monkeypatch, None)

    started = time.monotonic()
    with pytest.raises(PermissionError):
        ThreadStore(tmp_path / "comments.json").create("risk:1", "a")
    elapsed = time.monotonic() - started

    assert elapsed < 0.6  # gave up at the patched 0.1 s, not the real 1 s window
    assert len(calls) > 1
    assert list(tmp_path.glob("*.tmp")) == []


def test_other_write_errors_are_not_retried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[object] = []

    def fail(*args: object) -> None:
        calls.append(args)
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", fail)

    with pytest.raises(OSError, match="disk full"):
        ThreadStore(tmp_path / "comments.json").create("risk:1", "a")

    assert len(calls) == 1


def test_a_write_while_a_reader_holds_the_file_lands_once_it_lets_go(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "comments.json"
    store = ThreadStore(path)
    store.create("risk:1", "a")
    errors: list[BaseException] = []
    replacing = Event()
    real_replace = os.replace

    def spy(src: str, dst: Path) -> None:
        try:
            real_replace(src, dst)
        finally:  # after the real attempt, so on Windows the open handle has refused it first
            replacing.set()

    monkeypatch.setattr(os, "replace", spy)

    def write() -> None:
        try:
            store.create("risk:2", "b")
        except BaseException as error:  # noqa: BLE001 - reported by the assertion below
            errors.append(error)

    with path.open("rb"):
        writer = Thread_(target=write)
        writer.start()
        assert replacing.wait(timeout=5), "the writer never reached os.replace"
    writer.join()

    assert errors == []
    assert [t.anchor for t in store.all()] == ["risk:1", "risk:2"]


def test_a_broken_comments_json_is_reported_and_left_as_it_is(tmp_path: Path) -> None:
    path = tmp_path / "comments.json"
    path.write_bytes(b"{bad")
    store = ThreadStore(path)
    named = [f"{path.as_posix()}: Invalid JSON: key must be a string at line 1 column 2"]
    changes: list[Callable[[], object]] = [
        store.all,
        lambda: store.create("tab:plan", "hi"),
        lambda: store.reply("t-1", "hi", author="claude"),
        lambda: store.set_resolved("t-1", True),
    ]

    for change in changes:
        with pytest.raises(BrokenFile) as error:
            change()
        assert error.value.errors == named

    assert path.read_bytes() == b"{bad"


def test_resolve_is_refused_while_the_owner_has_the_last_word(
    store: ThreadStore, tmp_path: Path
) -> None:
    thread = store.create("class:A", "Why?")
    before = (tmp_path / "comments.json").read_bytes()

    with pytest.raises(threads.ResolveRefused):
        store.set_resolved(thread.id, True)

    assert (tmp_path / "comments.json").read_bytes() == before


def test_resolve_works_once_the_agent_has_replied(store: ThreadStore) -> None:
    thread = store.create("class:A", "Why?")
    store.reply(thread.id, "Because.", author="agent")

    assert store.set_resolved(thread.id, True).resolved


def test_a_reply_signed_with_the_old_author_counts_as_the_agent(store: ThreadStore) -> None:
    thread = store.create("class:A", "Why?")
    store.reply(thread.id, "Because.", author="claude")

    assert store.set_resolved(thread.id, True).resolved


def test_an_owner_follow_up_locks_resolve_again(store: ThreadStore) -> None:
    thread = store.create("class:A", "Why?")
    store.reply(thread.id, "Because.", author="agent")
    store.reply(thread.id, "But why?", author="owner")

    with pytest.raises(threads.ResolveRefused):
        store.set_resolved(thread.id, True)


def test_reopen_is_always_allowed(store: ThreadStore) -> None:
    thread = store.create("class:A", "Why?")
    store.reply(thread.id, "Because.", author="agent")
    store.set_resolved(thread.id, True)
    # an older file: resolved, with the owner speaking last
    path = store._path  # pyright: ignore[reportPrivateUsage]
    store.reply(thread.id, "Hm", author="owner")
    saved = store.all()
    saved[0].resolved = True
    path.write_bytes(threads._Threads.dump_json(saved))  # pyright: ignore[reportPrivateUsage]

    assert not store.set_resolved(thread.id, False).resolved


def test_an_owner_reply_reopens_a_resolved_thread(store: ThreadStore) -> None:
    thread = store.create("class:A", "Why?")
    store.reply(thread.id, "Because.", author="agent")
    store.set_resolved(thread.id, True)

    assert not store.reply(thread.id, "Wait", author="owner").resolved


def test_an_agent_reply_leaves_a_resolved_thread_resolved(store: ThreadStore) -> None:
    thread = store.create("class:A", "Why?")
    store.reply(thread.id, "Because.", author="agent")
    store.set_resolved(thread.id, True)

    assert store.reply(thread.id, "Also.", author="agent").resolved
