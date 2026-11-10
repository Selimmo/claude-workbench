from collections.abc import Callable
from pathlib import Path
from threading import Thread

import pytest

from plan_review.review.drafts import DraftNotFound, DraftStore
from plan_review.utils.json_files import BrokenFile


@pytest.fixture
def store(tmp_path: Path) -> DraftStore:
    return DraftStore(tmp_path / "drafts.json")


def test_a_new_draft_is_a_comment_on_its_anchor(store: DraftStore) -> None:
    draft = store.add("class:HintPolicy", "Why a class?")

    assert (draft.anchor, draft.text, draft.thread_id) == ("class:HintPolicy", "Why a class?", None)


def test_a_reply_draft_remembers_its_thread(store: DraftStore) -> None:
    draft = store.add("risk:1", "Agreed", thread_id="t-1")

    assert draft.thread_id == "t-1"


def test_drafts_persist_so_a_reload_finds_them(tmp_path: Path) -> None:
    path = tmp_path / "drafts.json"
    created = DraftStore(path).add("test:1", "Edge case?")

    assert DraftStore(path).all() == [created]


def test_a_draft_can_be_edited(store: DraftStore) -> None:
    draft = store.add("risk:1", "first")

    store.edit(draft.id, "first, reworded")

    assert [(d.id, d.text) for d in store.all()] == [(draft.id, "first, reworded")]


def test_discarding_a_draft_keeps_the_others(store: DraftStore) -> None:
    kept = store.add("risk:1", "first")
    gone = store.add("risk:2", "second")

    store.discard(gone.id)

    assert [d.id for d in store.all()] == [kept.id]


def test_discard_all_removes_exactly_those_drafts(store: DraftStore) -> None:
    a = store.add("risk:1", "a")
    b = store.add("risk:2", "b")
    c = store.add("risk:3", "c")

    store.discard_all({a.id, c.id})

    assert [d.id for d in store.all()] == [b.id]


@pytest.mark.parametrize("text", ["", "   \n"])
def test_a_blank_draft_is_refused(store: DraftStore, text: str) -> None:
    with pytest.raises(ValueError, match="empty"):
        store.add("risk:1", text)


@pytest.mark.parametrize("text", ["", "   \n"])
def test_a_draft_cannot_be_edited_to_blank(store: DraftStore, text: str) -> None:
    draft = store.add("risk:1", "real")

    with pytest.raises(ValueError, match="empty"):
        store.edit(draft.id, text)

    assert store.all()[0].text == "real"


def test_unknown_draft_id_raises_draft_not_found(store: DraftStore) -> None:
    with pytest.raises(DraftNotFound):
        store.discard("d-nope")


def run_together(*jobs: Callable[[], object]) -> None:
    workers = [Thread(target=job) for job in jobs]
    for w in workers:
        w.start()
    for w in workers:
        w.join()


def test_concurrent_new_drafts_are_all_kept(tmp_path: Path) -> None:
    path = tmp_path / "drafts.json"

    def add_many(prefix: str) -> None:
        store = DraftStore(path)  # e.g. two viewer tabs, each through its own request
        for i in range(40):
            store.add(f"{prefix}:{i}", "x")

    run_together(lambda: add_many("a"), lambda: add_many("b"))

    assert len(DraftStore(path).all()) == 80


def test_concurrent_edits_of_different_drafts_are_all_kept(tmp_path: Path) -> None:
    path = tmp_path / "drafts.json"
    first, second = DraftStore(path).add("risk:1", "x"), DraftStore(path).add("risk:2", "x")

    def grow(draft_id: str) -> None:
        # Each edit adds one character to this draft's own text: any edit lost to the
        # other writer leaves the text short.
        store = DraftStore(path)
        for _ in range(40):
            (mine,) = [d for d in store.all() if d.id == draft_id]
            store.edit(draft_id, mine.text + "x")

    run_together(lambda: grow(first.id), lambda: grow(second.id))

    assert [len(d.text) for d in DraftStore(path).all()] == [41, 41]


def test_concurrent_discards_of_different_drafts_all_take_effect(tmp_path: Path) -> None:
    path = tmp_path / "drafts.json"
    store = DraftStore(path)
    ids = [store.add(f"risk:{i}", "x").id for i in range(80)]

    def discard_each(some: list[str]) -> None:
        mine = DraftStore(path)
        for draft_id in some:
            mine.discard(draft_id)

    run_together(lambda: discard_each(ids[:40]), lambda: discard_each(ids[40:]))

    assert DraftStore(path).all() == []


def test_concurrent_discard_all_and_add_keep_the_new_draft(tmp_path: Path) -> None:
    path = tmp_path / "drafts.json"
    store = DraftStore(path)
    batches = [[store.add(f"risk:{i}", "x").id] for i in range(40)]

    def discard_batches() -> None:
        mine = DraftStore(path)
        for batch in batches:
            mine.discard_all(set(batch))

    def add_many() -> None:
        mine = DraftStore(path)
        for i in range(40):
            mine.add(f"new:{i}", "y")

    run_together(discard_batches, add_many)

    assert sorted(d.anchor for d in DraftStore(path).all()) == sorted(f"new:{i}" for i in range(40))


def test_a_broken_drafts_json_is_reported_and_left_as_it_is(tmp_path: Path) -> None:
    path = tmp_path / "drafts.json"
    path.write_bytes(b"{bad")
    store = DraftStore(path)
    named = [f"{path.as_posix()}: Invalid JSON: key must be a string at line 1 column 2"]
    changes: list[Callable[[], object]] = [
        store.all,
        lambda: store.add("tab:plan", "hi"),
        lambda: store.edit("d-1", "hi"),
        lambda: store.discard("d-1"),
        lambda: store.discard_all({"d-1"}),
    ]

    for change in changes:
        with pytest.raises(BrokenFile) as error:
            change()
        assert error.value.errors == named

    assert path.read_bytes() == b"{bad"
