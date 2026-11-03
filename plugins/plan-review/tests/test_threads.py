import os
import stat
from collections.abc import Callable
from pathlib import Path
from threading import Thread as Thread_

import pytest

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


def test_resolve_and_reopen_toggle_the_thread(store: ThreadStore) -> None:
    thread = store.create("risk:1", "Agreed")

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


def test_a_new_file_gets_the_usual_permissions_not_private_ones(tmp_path: Path) -> None:
    umask = os.umask(0)
    os.umask(umask)

    ThreadStore(tmp_path / "comments.json").create("risk:1", "a")

    assert stat.S_IMODE((tmp_path / "comments.json").stat().st_mode) == 0o666 & ~umask


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
