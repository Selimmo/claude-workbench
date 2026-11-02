from pathlib import Path

import pytest

from plan_review.threads import ThreadNotFound, ThreadStore


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
