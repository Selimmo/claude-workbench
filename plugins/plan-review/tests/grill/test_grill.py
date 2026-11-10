"""The grill: rounds of questions, the owner's answers, and the agent's turns."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from plan_review.grill.grill import (
    MAX_REPLIES,
    GrillError,
    GrillState,
    GrillStore,
    Question,
    SubmittedAnswer,
    load_grill,
)
from plan_review.grill.turn import Turn
from plan_review.review.threads import Message


def question(qid: str = "q1", *, choices: list[str] | None = None) -> dict[str, Any]:
    ids = choices if choices is not None else ["a", "b"]
    return {
        "id": qid,
        "title": f"Question {qid}?",
        "explanation": "Because.",
        "choices": [{"id": c, "label": f"Choice {c}", "description": f"About {c}"} for c in ids],
    }


def turn(**fields: Any) -> Turn:
    return Turn.model_validate(fields)


@pytest.fixture
def store(tmp_path: Path) -> GrillStore:
    return GrillStore(tmp_path / "grill.json")


def test_the_first_turn_creates_grill_json_with_its_title_and_round_1(store: GrillStore) -> None:
    state = store.post(turn(title="Add hints", round=[question()]))

    saved = json.loads(store._path.read_text())  # pyright: ignore[reportPrivateUsage]
    assert saved["title"] == "Add hints"
    assert saved["rounds"][0]["n"] == 1
    assert saved["rounds"][0]["questions"][0]["id"] == "q1"
    assert saved["rounds"][0]["questions"][0]["choices"][0]["description"] == "About a"
    assert state.open_questions()[0].id == "q1"


def test_a_first_turn_without_a_title_is_refused_and_writes_nothing(store: GrillStore) -> None:
    with pytest.raises(GrillError) as raised:
        store.post(turn(round=[question()]))

    assert raised.value.errors == ["title: required on the first turn"]
    assert not store._path.exists()  # pyright: ignore[reportPrivateUsage]


def test_a_question_needs_two_choices_and_unique_ids(store: GrillStore) -> None:
    with pytest.raises(GrillError) as raised:
        Turn.parse(
            json.dumps(
                {
                    "title": "T",
                    "round": [question("q1", choices=["a"]), question("q2", choices=["x", "x"])],
                }
            )
        )

    assert raised.value.errors == [
        "round.0.choices: needs at least two choices",
        "round.1.choices: choice ids must be unique",
    ]

    store.post(turn(title="T", round=[question("q1")]))
    with pytest.raises(GrillError) as reused:
        store.post(turn(round=[question("q1"), question("q2"), question("q2")]))

    assert reused.value.errors == [
        "round.0.id: 'q1' is already used by a question",
        "round.2.id: 'q2' is already used by a question",
    ]


def answer(qid: str, kind: str, **fields: Any) -> SubmittedAnswer:
    return SubmittedAnswer(question_id=qid, kind=kind, **fields)  # pyright: ignore[reportArgumentType]


def test_submitting_records_choices_and_their_notes_next_to_their_questions(
    store: GrillStore,
) -> None:
    store.post(turn(title="T", round=[question("q1"), question("q2")]))

    action = store.submit(
        [
            answer("q1", "choice", choice_id="b", text="only for now"),
            answer("q2", "choice", choice_id="a"),
        ]
    )

    state = store.get()
    first, second = state.rounds[0].questions
    assert (first.answer.kind, first.answer.choice_id, first.answer.text) == (  # pyright: ignore[reportOptionalMemberAccess]
        "choice",
        "b",
        "only for now",
    )
    assert (second.answer.kind, second.answer.choice_id, second.answer.text) == (  # pyright: ignore[reportOptionalMemberAccess]
        "choice",
        "a",
        None,
    )
    assert state.open_questions() == []
    assert [a.kind for a in state.log] == ["answers"]
    assert action.answers[0].question_id == "q1"


def test_an_other_answer_goes_into_the_thread_and_keeps_the_question_open(
    store: GrillStore,
) -> None:
    store.post(turn(title="T", round=[question("q1"), question("q2")]))

    store.submit(
        [
            answer("q1", "other", text="What does a hint cost?"),
            answer("q2", "choice", choice_id="a"),
        ]
    )

    asked = store.get().open_questions()[0]
    assert asked.id == "q1"
    assert asked.answer is None
    assert [(m.author, m.text) for m in asked.thread] == [("owner", "What does a hint cost?")]
    assert asked.awaiting_reply()


def snapshot(store: GrillStore) -> str:
    return store._path.read_text()  # pyright: ignore[reportPrivateUsage]


@pytest.mark.parametrize(
    ("answers", "error"),
    [
        ([answer("q1", "choice", choice_id="a")], "q2: needs a response"),
        (
            [
                answer("q1", "choice", choice_id="a"),
                answer("q1", "choice", choice_id="zz"),
                answer("q2", "other", text="fine"),
            ],
            "answers.1.question_id: 'q1' is answered twice",
        ),
        (
            [
                answer("q1", "other", text="x"),
                answer("q2", "other", text="fine"),
                answer("q9", "other", text="x"),
            ],
            "answers.2.question_id: no open question 'q9'",
        ),
        (
            [
                answer("q1", "other", text="x"),
                answer("q2", "other", text="fine"),
                answer("q9", "choice", choice_id="a"),
            ],
            "answers.2.question_id: no open question 'q9'",
        ),
        (
            [answer("q1", "choice", choice_id="zz"), answer("q2", "other", text="fine")],
            "answers.0.choice_id: 'zz' is not a choice of 'q1'",
        ),
        (
            [answer("q1", "choice"), answer("q2", "other", text="fine")],
            "answers.0.choice_id: needed to pick a choice",
        ),
        (
            [answer("q1", "other", text="  "), answer("q2", "choice", choice_id="a")],
            "answers.0.text: needed for Other",
        ),
        (
            [answer("q1", "other", text=""), answer("q2", "other", text="fine")],
            "answers.0.text: needed for Other",
        ),
    ],
)
def test_a_submit_needs_exactly_one_valid_response_per_open_question(
    store: GrillStore, answers: list[SubmittedAnswer], error: str
) -> None:
    store.post(turn(title="T", round=[question("q1"), question("q2")]))
    before = snapshot(store)

    with pytest.raises(GrillError) as raised:
        store.submit(answers)

    assert raised.value.errors == [error]
    assert not raised.value.conflict
    assert snapshot(store) == before


@pytest.mark.parametrize("kind", ["own", "ask"])
def test_own_and_ask_submissions_are_no_longer_accepted(store: GrillStore, kind: str) -> None:
    store.post(turn(title="T", round=[question("q1"), question("q2")]))
    before = snapshot(store)

    with pytest.raises(GrillError) as raised:
        store.submit([answer("q1", kind, text="x"), answer("q2", "choice", choice_id="a")])

    assert raised.value.errors == [
        f"answers.0.kind: '{kind}' is no longer accepted; pick a choice or Other"
    ]
    assert not raised.value.conflict
    assert snapshot(store) == before


def test_a_grill_json_from_0_1_9_with_own_and_ask_still_loads(tmp_path: Path) -> None:
    old = json.loads((Path(__file__).parents[1] / "fixtures" / "grill-0.1.9.json").read_text())
    old["handled"] = 0  # so that pending() has the owner's logged answers to describe
    path = tmp_path / "grill.json"
    path.write_text(json.dumps(old))

    store = GrillStore(path)
    state = store.get()

    own = state.question("q-hint-source").answer
    assert own is not None
    assert (own.kind, own.text) == (
        "own",
        "Written, and the author can mark a question as hint-free.",
    )
    asked = state.question("q-hint-cost")
    assert [m.author for m in asked.thread] == ["owner", "claude"]
    kinds = [[a["kind"] for a in action["answers"]] for action in store.pending()]
    assert kinds == [["ask", "own"], ["choice"]]
    assert [a.kind for a in state.log[0].answers] == ["ask", "own"]


def ask_other(store: GrillStore, qid: str = "q1", text: str = "Something else?") -> None:
    store.submit([answer(qid, "other", text=text)])


def test_a_decision_for_an_awaiting_question_settles_it_with_the_other_text(
    store: GrillStore,
) -> None:
    store.post(turn(title="T", round=[question("q1")]))
    ask_other(store, text="A third way")

    state = store.post(turn(decisions=[decision("d1", question_id="q1")], round=[question("q2")]))

    settled = state.question("q1")
    assert settled.answer is not None
    assert (settled.answer.kind, settled.answer.choice_id, settled.answer.text) == (
        "other",
        None,
        "A third way",
    )
    assert [q.id for q in state.open_questions()] == ["q2"]


def test_an_awaiting_question_needs_one_reply_or_one_settling_decision_not_both(
    store: GrillStore,
) -> None:
    store.post(turn(title="T", round=[question("q1"), question("q2")]))
    store.submit([answer("q1", "other", text="x"), answer("q2", "other", text="y")])
    before = snapshot(store)
    reply = {"question_id": "q1", "text": "r"}

    with pytest.raises(GrillError) as neither:
        store.post(turn(replies=[reply]))
    assert neither.value.errors == ["replies: question 'q2' is awaiting a reply or a decision"]

    with pytest.raises(GrillError) as both:
        store.post(turn(replies=[reply], decisions=[decision("d1", question_id="q1")]))
    assert both.value.errors == [
        "replies: question 'q1' is replied to and settled in one turn; do one of them",
        "replies: question 'q2' is awaiting a reply or a decision",
    ]
    assert snapshot(store) == before

    state = store.post(turn(replies=[reply], decisions=[decision("d1", question_id="q2")]))
    assert [q.id for q in state.open_questions()] == ["q1"]


def test_a_decision_for_a_question_with_no_other_pending_does_not_close_it(
    store: GrillStore,
) -> None:
    store.post(turn(title="T", round=[question("q1")]))

    state = store.post(turn(decisions=[decision("d1", question_id="q1")]))

    assert [q.id for q in state.open_questions()] == ["q1"]


def reply_three_times(store: GrillStore) -> None:
    for i in range(MAX_REPLIES):
        ask_other(store, text=f"other {i}")
        store.post(turn(replies=[{"question_id": "q1", "text": f"reply {i}"}]))


def test_after_three_replies_an_other_is_still_accepted_and_must_be_settled(
    store: GrillStore,
) -> None:
    store.post(turn(title="T", round=[question("q1")]))
    reply_three_times(store)
    assert not store.get().question("q1").awaiting_reply()

    ask_other(store, text="my final word")  # a 4th Other is accepted
    question_1 = store.get().question("q1")
    assert question_1.must_settle()
    before = snapshot(store)

    with pytest.raises(GrillError) as raised:
        store.post(turn(replies=[{"question_id": "q1", "text": "one more"}]))
    assert raised.value.errors == [
        "replies.0.question_id: question 'q1' has had 3 replies; it must be settled with a decision"
    ]
    assert snapshot(store) == before

    state = store.post(turn(decisions=[decision("d1", question_id="q1")], done=True))
    answer_1 = state.question("q1").answer
    assert answer_1 is not None
    assert (answer_1.kind, answer_1.text) == ("other", "my final word")


def test_settling_the_last_open_question_and_done_in_one_turn_is_accepted(
    store: GrillStore,
) -> None:
    store.post(turn(title="T", round=[question("q1")]))
    ask_other(store)

    state = store.post(turn(decisions=[decision("d1", question_id="q1")], done=True))

    assert state.done
    assert state.open_questions() == []


def test_pending_marks_an_other_that_must_be_settled(store: GrillStore) -> None:
    store.post(turn(title="T", round=[question("q1")]))
    ask_other(store, text="first")
    [first] = store.pending()
    assert first["answers"] == [
        {"question_id": "q1", "question": "Question q1?", "kind": "other", "text": "first"}
    ]
    store.post(turn(replies=[{"question_id": "q1", "text": "r0"}]))
    for i in range(1, MAX_REPLIES):
        ask_other(store, text=f"other {i}")
        store.post(turn(replies=[{"question_id": "q1", "text": f"r{i}"}]))
    ask_other(store, text="final")

    [last] = store.pending()
    assert last["answers"][0]["must_settle"] is True


def test_pending_does_not_mark_a_choice_on_a_question_with_all_its_replies(
    store: GrillStore,
) -> None:
    store.post(turn(title="T", round=[question("q1")]))
    for i in range(MAX_REPLIES):
        ask_other(store, text=f"other {i}")
        store.post(turn(replies=[{"question_id": "q1", "text": f"r{i}"}]))
    store.submit([answer("q1", "choice", choice_id="a")])

    [picked] = store.pending()
    assert picked["answers"][0]["kind"] == "choice"
    assert "must_settle" not in picked["answers"][0]


def test_the_owner_cannot_submit_while_claude_has_unhandled_actions(store: GrillStore) -> None:
    state = store.post(turn(title="T", round=[question("q1")]))
    assert state.owners_turn()

    store.submit([answer("q1", "choice", choice_id="a")])
    assert not store.get().owners_turn()
    before = snapshot(store)

    with pytest.raises(GrillError) as raised:
        store.submit([answer("q1", "other", text="again")])

    assert raised.value.conflict
    assert raised.value.errors == ["waiting for the agent to handle your last action"]
    assert snapshot(store) == before

    store.post(turn(round=[question("q2")]))
    assert store.get().owners_turn()


def test_a_reply_to_an_other_keeps_the_question_open_for_another_pick(
    store: GrillStore,
) -> None:
    store.post(turn(title="T", round=[question("q1"), question("q2")]))
    store.submit(
        [
            answer("q1", "other", text="What does a hint cost?"),
            answer("q2", "choice", choice_id="a"),
        ]
    )

    asked = store.get().open_questions()[0]
    assert [(m.author, m.text) for m in asked.thread] == [("owner", "What does a hint cost?")]
    assert asked.awaiting_reply()

    with pytest.raises(GrillError) as raised:
        store.post(turn(round=[question("q3")]))
    assert raised.value.errors == ["replies: question 'q1' is awaiting a reply or a decision"]

    twice = {"question_id": "q1", "text": "One request."}
    with pytest.raises(GrillError) as doubled:
        store.post(turn(replies=[twice, twice]))
    assert doubled.value.errors == ["replies.1.question_id: 'q1' is not awaiting a reply"]

    state = store.post(turn(replies=[twice]))
    replied = state.open_questions()[0]
    assert [(m.author, m.text) for m in replied.thread][-1] == ("agent", "One request.")
    assert not replied.awaiting_reply()
    assert replied.replies() == 1

    store.submit([answer("q1", "choice", choice_id="b")])
    assert store.get().open_questions() == []


REVISED = {
    "explanation": "Now clearer.",
    "choices": [
        {"id": "n1", "label": "New 1", "description": ""},
        {"id": "n2", "label": "New 2", "description": ""},
    ],
}


def test_a_reply_may_revise_an_open_question(store: GrillStore) -> None:
    store.post(turn(title="T", round=[question("q1"), question("q2")]))
    store.submit([answer("q1", "other", text="Which?"), answer("q2", "choice", choice_id="a")])

    state = store.post(
        turn(replies=[{"question_id": "q1", "text": "See below.", "revised": REVISED}])
    )

    q1 = state.open_questions()[0]
    assert q1.updated
    assert q1.explanation == "Now clearer."
    assert [c.id for c in q1.choices] == ["n1", "n2"]


@pytest.mark.parametrize("target", ["q1", "q2"])  # q1 has no pending ask; q2 is answered
def test_a_reply_cannot_revise_a_question_that_is_not_awaiting_one(
    store: GrillStore, target: str
) -> None:
    store.post(turn(title="T", round=[question("q1"), question("q2")]))
    store.submit([answer("q1", "other", text="Which?"), answer("q2", "choice", choice_id="a")])
    store.post(turn(replies=[{"question_id": "q1", "text": "See below."}]))
    before = snapshot(store)

    with pytest.raises(GrillError) as raised:
        store.post(turn(replies=[{"question_id": target, "text": "x", "revised": REVISED}]))

    assert raised.value.errors == [f"replies.0.question_id: '{target}' is not awaiting a reply"]
    assert snapshot(store) == before


def decision(did: str, **fields: Any) -> dict[str, Any]:
    return {"id": did, "topic": "Hints", "decision": f"Decision {did}", "choice": "Yes", **fields}


def test_decisions_have_ids_and_can_replace_earlier_ones(store: GrillStore) -> None:
    store.post(
        turn(title="T", round=[question("q1")], decisions=[decision("d1", question_id="q1")])
    )

    state = store.post(turn(decisions=[decision("d2", replaces="d1", why="Changed my mind")]))

    assert [d.id for d in state.decisions] == ["d1", "d2"]
    assert state.decisions[1].replaces == "d1"


@pytest.mark.parametrize(
    ("bad", "error"),
    [
        ([decision("d2")], "decisions.0.id: 'd2' is already used by a decision"),
        ([decision("d3", replaces="nope")], "decisions.0.replaces: no decision 'nope'"),
        ([decision("d3", replaces="d1")], "decisions.0.replaces: 'd1' is already replaced"),
        ([decision("d3", question_id="nope")], "decisions.0.question_id: no question 'nope'"),
        (
            [decision("d6"), decision("d6")],
            "decisions.1.id: 'd6' is already used by a decision",
        ),
        (
            [decision("d6", replaces="d5"), decision("d7", replaces="d5")],
            "decisions.1.replaces: 'd5' is already replaced",
        ),
    ],
)
def test_a_decision_with_a_bad_id_or_reference_is_refused(
    store: GrillStore, bad: list[dict[str, Any]], error: str
) -> None:
    store.post(
        turn(
            title="T",
            round=[question("q1")],
            decisions=[decision("d1"), decision("d2", replaces="d1"), decision("d5")],
        )
    )
    before = snapshot(store)

    with pytest.raises(GrillError) as raised:
        store.post(turn(decisions=bad))

    assert raised.value.errors == [error]
    assert snapshot(store) == before


@pytest.mark.parametrize(
    ("bad", "error"),
    [
        (turn(done=True), "done: questions are still open: q1"),
        (turn(done=True, round=[question("q2")]), "done: questions are still open: q1, q2"),
    ],
)
def test_done_needs_an_empty_frontier(store: GrillStore, bad: Turn, error: str) -> None:
    store.post(turn(title="T", round=[question("q1")]))
    before = snapshot(store)

    with pytest.raises(GrillError) as raised:
        store.post(bad)

    assert raised.value.errors == [error]
    assert snapshot(store) == before


def test_every_turn_leaves_the_owner_something_or_says_done(store: GrillStore) -> None:
    store.post(turn(title="T", round=[question("q1")]))
    store.submit([answer("q1", "choice", choice_id="a")])
    before = snapshot(store)

    with pytest.raises(GrillError) as nothing:
        store.post(turn(out_of_scope=["Rate limiting"]))
    assert nothing.value.errors == [
        "round: nothing is left for the owner; post a round, answer an Other or set done"
    ]
    assert snapshot(store) == before

    state = store.post(turn(out_of_scope=["Rate limiting"], done=True))
    assert state.done
    assert state.out_of_scope == ["Rate limiting"]


def test_a_decisions_only_turn_after_done_is_accepted_and_the_grill_stays_done(
    store: GrillStore,
) -> None:
    store.post(turn(title="T", round=[question("q1")]))
    store.submit([answer("q1", "choice", choice_id="a")])
    store.post(turn(done=True))

    state = store.post(turn(decisions=[decision("d1")]))

    assert state.done
    assert [d.id for d in state.decisions] == ["d1"]


def test_the_owner_cannot_submit_once_the_grill_is_done(store: GrillStore) -> None:
    store.post(turn(title="T", round=[question("q1")]))
    store.submit([answer("q1", "choice", choice_id="a")])
    store.post(turn(done=True))
    before = snapshot(store)

    with pytest.raises(GrillError) as raised:
        store.submit([])

    assert raised.value.conflict
    assert raised.value.errors == ["the grill is done: confirm it or say 'not yet'"]
    assert snapshot(store) == before


def test_pending_lists_owner_actions_the_agent_has_not_answered(store: GrillStore) -> None:
    store.post(turn(title="T", round=[question("q1"), question("q2"), question("q3")]))
    assert store.pending() == []

    store.submit(
        [
            answer("q1", "choice", choice_id="b", text="note"),
            answer("q2", "other", text="Why?"),
            answer("q3", "choice", choice_id="a"),
        ]
    )

    [action] = store.pending()
    assert action["kind"] == "answers"
    assert action["answers"] == [
        {
            "question_id": "q1",
            "question": "Question q1?",
            "kind": "choice",
            "choice_id": "b",
            "choice": "Choice b",
            "text": "note",
        },
        {"question_id": "q2", "question": "Question q2?", "kind": "other", "text": "Why?"},
        {
            "question_id": "q3",
            "question": "Question q3?",
            "kind": "choice",
            "choice_id": "a",
            "choice": "Choice a",
        },
    ]

    state = store.post(turn(replies=[{"question_id": "q2", "text": "Because."}]))
    assert state.handled == len(state.log) == 1
    assert store.pending() == []


def test_confirm_needs_done_and_reopen_brings_grilling_back(store: GrillStore) -> None:
    store.post(turn(title="T", round=[question("q1")]))
    with pytest.raises(GrillError) as early:
        store.confirm()
    assert early.value.conflict

    store.submit([answer("q1", "choice", choice_id="a")])
    store.post(turn(done=True))
    assert store.get().done

    with pytest.raises(GrillError) as blank:
        store.reopen("  ")
    assert not blank.value.conflict

    store.reopen("Also ask about caching")
    state = store.get()
    assert not state.done
    assert [a.kind for a in state.log] == ["answers", "reopen"]
    assert state.log[1].text == "Also ask about caching"
    assert [p["text"] for p in store.pending()] == ["Also ask about caching"]

    store.post(turn(done=True))
    store.confirm()
    state = store.get()
    assert state.confirmed_at is not None
    assert not state.owners_turn()
    assert [p["kind"] for p in store.pending()] == ["confirm"]


@pytest.mark.parametrize(
    "refused",
    [
        lambda store: store.confirm(),
        lambda store: store.reopen("more"),
        lambda store: store.submit([]),
        lambda store: store.post(turn(round=[question("q9")])),
    ],
    ids=["confirm", "reopen", "submit", "post"],
)
def test_nothing_is_accepted_once_the_owner_confirmed(
    store: GrillStore, refused: Callable[[GrillStore], object]
) -> None:
    store.post(turn(title="T", round=[question("q1")]))
    store.submit([answer("q1", "choice", choice_id="a")])
    store.post(turn(done=True))
    store.confirm()
    before = snapshot(store)

    with pytest.raises(GrillError) as raised:
        refused(store)

    assert raised.value.conflict
    assert raised.value.errors == ["the owner already confirmed the grill"]
    assert snapshot(store) == before


def test_a_misspelled_key_inside_a_choice_or_decision_is_refused() -> None:
    typo_choice = {**question(), "choices": [{"id": "a", "label": "A", "descripton": "x"}] * 2}
    with pytest.raises(GrillError) as raised:
        Turn.parse(json.dumps({"title": "T", "round": [typo_choice]}))
    assert "Extra inputs are not permitted" in "\n".join(raised.value.errors)

    typo_decision = {"id": "d2", "topic": "t", "decision": "d", "choice": "c", "replace": "d1"}
    with pytest.raises(GrillError) as raised:
        Turn.parse(json.dumps({"title": "T", "decisions": [typo_decision]}))
    assert "decisions.0.replace: Extra inputs are not permitted" in raised.value.errors


def test_a_grill_json_that_does_not_parse_is_a_grill_error(tmp_path: Path) -> None:
    path = tmp_path / "grill.json"
    path.write_text("{bad")

    with pytest.raises(GrillError) as raised:
        GrillStore(path).get()

    assert raised.value.errors


def test_load_grill_names_the_file_in_every_error_line(tmp_path: Path) -> None:
    path = tmp_path / "grill.json"
    path.write_text("{bad")
    with pytest.raises(GrillError) as bad_json:
        load_grill(path)
    assert bad_json.value.errors == [
        f"{path.as_posix()}: Invalid JSON: key must be a string at line 1 column 2"
    ]

    path.write_text("{}")
    with pytest.raises(GrillError) as no_title:
        load_grill(path)
    assert no_title.value.errors == [f"{path.as_posix()}: title: Field required"]


EXAMPLES = Path(__file__).parents[2] / "examples"


def used_kinds(state: GrillState) -> set[str]:
    kinds = {a.kind for a in state.log for a in a.answers}
    kinds |= {q.answer.kind for r in state.rounds for q in r.questions if q.answer}
    return kinds


def test_the_example_grills_load_as_an_open_round_and_a_done_grill() -> None:
    demo = load_grill(EXAMPLES / "grill.json")
    questions = {q.id: q for r in demo.rounds for q in r.questions}

    assert demo.owners_turn()
    assert not demo.done
    settled = [q for q in questions.values() if q.answer and q.answer.kind == "other"]
    assert [q.id for q in settled] == ["q-hint-source"]
    replied = [q for q in demo.open_questions() if q.replies() == 1 and not q.must_settle()]
    assert replied
    assert [q.id for q in demo.open_questions() if q.must_settle()] == ["q-hint-final"]
    assert any(not q.thread for q in demo.open_questions())
    assert used_kinds(demo) <= {"choice", "other"}

    done = load_grill(EXAMPLES / "grill-done.json")
    assert done.done
    assert done.confirmed_at is None
    assert done.owners_turn()
    assert done.open_questions() == []
    assert used_kinds(done) <= {"choice", "other"}
    assert [d.id for d in done.decisions] == [d.id for d in demo.decisions]


def test_replies_from_both_authors_count_toward_the_limit() -> None:
    thread = [
        Message(author="owner", text="why?"),
        Message(author="claude", text="old 1"),
        Message(author="claude", text="old 2"),
        Message(author="owner", text="and?"),
        Message(author="agent", text="new"),
    ]
    q = Question.model_validate({**question("q1"), "thread": thread})

    assert q.replies() == 3
    assert q.must_settle() is True


def test_grill_refusals_say_the_agent(store: GrillStore) -> None:
    store.post(turn(title="T", round=[question("q1")]))
    with pytest.raises(GrillError) as too_early:
        store.confirm()
    store.submit([answer("q1", "choice", choice_id="a")])
    with pytest.raises(GrillError) as out_of_turn:
        store.submit([answer("q1", "other", text="again")])

    assert out_of_turn.value.errors == ["waiting for the agent to handle your last action"]
    assert too_early.value.errors == ["The agent has not said the grill is done yet"]
