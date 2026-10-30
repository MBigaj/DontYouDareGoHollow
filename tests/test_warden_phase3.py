"""The Warden's third phase: a conversation typed in the fight, judged later by the Sensei."""

import re
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from hollow.adapters.db.store import SqlEventStore
from hollow.application.agents import AgentDesk, AgentError
from hollow.application.fights import FightError, FightService
from hollow.domain.bosses import (
    FIRST_TRY_BONUS,
    PASS_REPLIES,
    SOULS_PER_HIT,
    VICTORY_SOULS,
    WARDEN,
    Attempt,
    Beat,
    Kind,
    Outcome,
    Question,
    lines,
    spoken,
    verdict_task,
)
from hollow.domain.conjugation import Verb
from hollow.domain.events import AgentResult, Event, FightAction, FightStarted, FightTurn
from hollow.domain.world import WorldState, replay
from tests.conftest import FakeClock
from tests.test_web_lessons import learn
from tests.test_world import CAL

HX = {"HX-Request": "true"}
SENTENCE = "水を飲んでください。"


def state(store: SqlEventStore, clock: FakeClock) -> WorldState:
    return replay(store.all(), CAL, CAL.day_of(clock.now()))


def current(store: SqlEventStore, clock: FakeClock) -> Attempt:
    attempt = state(store, clock).bosses[WARDEN.id].current
    assert attempt is not None
    return attempt


def to_phase_three(store: SqlEventStore, clock: FakeClock) -> Attempt:
    """Learns the verbs, enters the fog and wins phases 1 and 2."""
    learn(store, clock)
    fights = FightService(store, clock, CAL)
    view = fights.enter(WARDEN.id)
    while (attempt := view.record.current) is not None and not attempt.conversing:
        clock.advance(seconds=2)
        assert view.question is not None
        view = fights.answer(WARDEN.id, str(attempt.id), attempt.turns, view.question.answers[1])
    return current(store, clock)


def reply_all(store: SqlEventStore, clock: FakeClock, text: str = SENTENCE) -> Attempt:
    fights = FightService(store, clock, CAL)
    while not (attempt := current(store, clock)).judging:
        clock.advance(seconds=2)
        fights.reply(WARDEN.id, str(attempt.id), len(attempt.replies), text)
    return current(store, clock)


def result(attempt: Attempt, good: int, passed: bool | None = None) -> dict[str, Any]:
    turns = [
        {"prompt": "…", "reply": reply, "ok": n < good} for n, reply in enumerate(attempt.replies)
    ]
    return {
        "agent": "sensei",
        "task": verdict_task(attempt),
        "passed": good >= PASS_REPLIES if passed is None else passed,
        "turns": turns,
        "corrections": [
            {"wrote": "飲むでください", "better": "飲んでください", "why": "む → んで."}
        ],
    }


# --- the phase ----------------------------------------------------------------


def test_the_warden_has_a_third_phase_that_speaks() -> None:
    third = WARDEN.phases[2]
    assert third.conversation and third.prompts == 4 and PASS_REPLIES == 3
    assert "Phase 3" in WARDEN.intro


def test_phase_two_falls_into_the_conversation(store: SqlEventStore, clock: FakeClock) -> None:
    attempt = to_phase_three(store, clock)
    assert (attempt.phase, attempt.beat, attempt.prompts) == (2, Beat.PHASE, 4)
    assert attempt.conversing and not attempt.judging and not attempt.can_drink


def test_lines_are_requests_and_sequences_of_known_verbs(
    store: SqlEventStore, clock: FakeClock
) -> None:
    attempt = to_phase_three(store, clock)
    fights = FightService(store, clock, CAL)
    said = lines(WARDEN, attempt, fights.verbs())
    assert len(said) == 4 and {q.kind for q in said} == {Kind.REQUEST, Kind.SEQUENCE}
    assert said == lines(WARDEN, attempt, fights.verbs())  # the same seed says the same
    request = Question(Kind.REQUEST, (Verb("開ける", "あける", "to open (a door)"),))
    sequence = Question(
        Kind.SEQUENCE, (Verb("起きる", "おきる", "to wake up"), Verb("食べる", "たべる", "to eat"))
    )
    assert spoken(request) == "Ask me, politely, to open (開ける)."
    assert spoken(sequence) == (
        "Tell me what you do: first you wake up (起きる), then you eat (食べる)."
    )


def test_replies_wait_for_the_sensei(store: SqlEventStore, clock: FakeClock) -> None:
    attempt = to_phase_three(store, clock)
    for action in (FightAction.ANSWER, FightAction.ESTUS):  # nothing else counts now
        clock.advance(seconds=1)
        store.append(FightTurn(clock.now(), attempt.id, action, True))
    assert current(store, clock).replies == ()
    judging = reply_all(store, clock)
    assert judging.judging and judging.beat is Beat.JUDGING and judging.replies == (SENTENCE,) * 4
    clock.advance(seconds=1)
    store.append(FightTurn(clock.now(), attempt.id, FightAction.REPLY, text="more"))
    assert current(store, clock).replies == (SENTENCE,) * 4
    assert not state(store, clock).bosses[WARDEN.id].defeated


def test_a_pass_fells_the_warden_and_pays(store: SqlEventStore, clock: FakeClock) -> None:
    to_phase_three(store, clock)
    judging = reply_all(store, clock)
    before = state(store, clock)
    AgentDesk(store, clock, CAL).submit(result(judging, good=3))
    after = state(store, clock)
    record = after.bosses[WARDEN.id]
    assert record.defeated and record.last is not None and record.last.outcome is Outcome.WON
    assert after.souls - before.souls == 3 * SOULS_PER_HIT + VICTORY_SOULS + FIRST_TRY_BONUS
    assert after.armory.owns("warden-maul") and after.armory.owns_armour("warden-pauldrons")


def test_a_fail_kills_you_and_the_retry_starts_at_the_question(
    store: SqlEventStore, clock: FakeClock
) -> None:
    to_phase_three(store, clock)
    judging = reply_all(store, clock)
    before = state(store, clock).souls
    AgentDesk(store, clock, CAL).submit(result(judging, good=2))
    world = state(store, clock)
    record = world.bosses[WARDEN.id]
    assert not record.defeated and record.deaths == 1 and record.current is None
    assert world.souls - before == 2 * SOULS_PER_HIT  # good replies still pay
    clock.advance(seconds=5)
    retry = FightService(store, clock, CAL).enter(WARDEN.id).attempt
    assert retry is not None and retry.phase == 2 and retry.conversing and retry.number == 2
    assert retry.wound == pytest.approx(0.9)


def test_attempts_keep_the_phases_they_began_with(store: SqlEventStore, clock: FakeClock) -> None:
    """An attempt stored with two phases (before phase 3 existed) still wins at phase 2."""
    started = FightStarted(clock.now(), WARDEN.id, 1, 100, 35, phases=2)
    store.append(started)
    while (attempt := state(store, clock).bosses[WARDEN.id].current) is not None:
        assert not attempt.conversing
        clock.advance(seconds=1)
        store.append(FightTurn(clock.now(), started.id, FightAction.ANSWER, True))
    assert state(store, clock).bosses[WARDEN.id].defeated


def test_a_verdict_for_another_attempt_changes_nothing(
    store: SqlEventStore, clock: FakeClock
) -> None:
    to_phase_three(store, clock)
    judging = reply_all(store, clock)
    clock.advance(seconds=1)
    payload = result(judging, good=4)
    store.append(AgentResult(clock.now(), "sensei", "boss:te-warden:other:phase-3", payload))
    assert current(store, clock).judging


def test_replies_and_phase_counts_round_trip_through_the_store(
    store: SqlEventStore, clock: FakeClock
) -> None:
    started = FightStarted(clock.now(), WARDEN.id, 7, 110, 34, 12, 3, phases=3)
    events: list[Event] = [
        started,
        FightTurn(clock.now() + timedelta(seconds=1), started.id, FightAction.REPLY, text=SENTENCE),
    ]
    for event in events:
        store.append(event)
    assert list(store.all()) == events


# --- the service --------------------------------------------------------------


def test_the_service_takes_one_reply_per_line(store: SqlEventStore, clock: FakeClock) -> None:
    attempt = to_phase_three(store, clock)
    fights = FightService(store, clock, CAL)
    with pytest.raises(FightError, match="whole sentence"):
        fights.reply(WARDEN.id, str(attempt.id), 0, "   ")
    with pytest.raises(FightError, match="one sentence"):
        fights.reply(WARDEN.id, str(attempt.id), 0, "あ" * 121)
    fights.reply(WARDEN.id, str(attempt.id), 0, "  水を   飲んでください。 ")
    fights.reply(WARDEN.id, str(attempt.id), 0, SENTENCE)  # a double submit
    assert current(store, clock).replies == ("水を 飲んでください。",)
    view = fights.answer(WARDEN.id, str(attempt.id), attempt.turns, "x")  # not a quiz now
    assert view.answered is None


# --- the Sensei ---------------------------------------------------------------


def test_the_inbox_hands_the_sensei_the_transcript(store: SqlEventStore, clock: FakeClock) -> None:
    to_phase_three(store, clock)
    desk = AgentDesk(store, clock, CAL)
    assert not [t for t in desk.inbox()["tasks"] if t["task"].startswith("boss:")]
    judging = reply_all(store, clock)
    (task,) = [t for t in desk.inbox()["tasks"] if t["task"].startswith("boss:")]
    assert task["agent"] == "sensei" and task["task"] == verdict_task(judging)
    assert task["pass"] == "3 good replies of 4" and "てください" in task["rubric"]
    assert [t["reply"] for t in task["transcript"]] == [SENTENCE] * 4
    assert all(t["line"] and t["verbs"] for t in task["transcript"])


def test_the_desk_checks_the_verdict_against_the_fight(
    store: SqlEventStore, clock: FakeClock
) -> None:
    to_phase_three(store, clock)
    desk = AgentDesk(store, clock, CAL)
    attempt = current(store, clock)
    with pytest.raises(AgentError, match="No conversation is waiting"):
        desk.submit(result(attempt, good=4))  # not every line answered yet
    judging = reply_all(store, clock)
    wrong_reply = result(judging, good=4)
    wrong_reply["turns"][1]["reply"] = "something else"
    with pytest.raises(AgentError, match="word for word"):
        desk.submit(wrong_reply)
    with pytest.raises(AgentError, match="2 good replies do not pass"):
        desk.submit(result(judging, good=2, passed=True))
    with pytest.raises(AgentError, match="No boss called"):
        desk.submit({**result(judging, good=4), "task": f"boss:nobody:{judging.id}:phase-3"})
    desk.submit(result(judging, good=4))
    with pytest.raises(AgentError, match="No conversation is waiting"):
        desk.submit(result(judging, good=4))  # judged once


# --- the page -----------------------------------------------------------------


def fields(page: str) -> dict[str, str]:
    return dict(re.findall(r'<input type="hidden" name="(\w+)" value="([^"]*)">', page))


def test_the_fight_page_speaks_takes_replies_and_waits(
    client: TestClient, store: SqlEventStore, clock: FakeClock
) -> None:
    to_phase_three(store, clock)
    page = client.get("/boss/te-warden").text
    assert "Phase 3 of 3" in page and "The Warden speaks · line 1 of 4" in page
    assert 'action="/boss/te-warden/reply"' in page and "Drink Estus" not in page
    empty = client.post("/boss/te-warden/reply", data={**fields(page), "reply": ""}, headers=HX)
    assert "whole sentence" in empty.text
    for n in range(4):
        page = client.post(
            "/boss/te-warden/reply", data={**fields(page), "reply": SENTENCE}, headers=HX
        ).text
        if n < 3:
            assert f"line {n + 2} of 4" in page
    assert "weighs your words" in page and page.count(SENTENCE) == 4
    assert "agent round" in page


def test_the_gate_shows_the_senseis_verdict(
    client: TestClient, store: SqlEventStore, clock: FakeClock
) -> None:
    to_phase_three(store, clock)
    judging = reply_all(store, clock)
    AgentDesk(store, clock, CAL).submit(result(judging, good=2))
    gate = client.get("/boss/te-warden").text
    assert "The Sensei's verdict" in gate and "The Warden struck you down" in gate
    assert "2 of 4 replies held; 3 were needed" in gate and "飲んでください" in gate
    assert "Enter the fog" in gate


def test_replies_without_javascript_redirect(
    client: TestClient, store: SqlEventStore, clock: FakeClock
) -> None:
    to_phase_three(store, clock)
    page = client.get("/boss/te-warden").text
    response = client.post(
        "/boss/te-warden/reply", data={**fields(page), "reply": SENTENCE}, follow_redirects=False
    )
    assert response.headers["location"] == "/boss/te-warden"
    assert current(store, clock).replies == (SENTENCE,)
