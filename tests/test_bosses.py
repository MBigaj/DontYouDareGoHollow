import re
from datetime import timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from hollow.adapters.db.store import SqlEventStore
from hollow.application.agents import AgentDesk
from hollow.application.fights import FightError, FightService
from hollow.domain.activities import Track
from hollow.domain.bosses import (
    DAMAGE,
    VICTORY_SOULS,
    WARDEN,
    Attempt,
    Beat,
    BossRecord,
    Kind,
    Outcome,
    Question,
    question,
    verdict_task,
)
from hollow.domain.conjugation import Verb
from hollow.domain.events import FightAction, FightStarted, FightTurn
from hollow.domain.world import replay
from tests.conftest import FakeClock
from tests.test_lessons import DECK_VERBS
from tests.test_web_lessons import learn
from tests.test_world import CAL

HX = {"HX-Request": "true"}
VERBS = [Verb(w, k, "meaning") for w, k in DECK_VERBS]
P1, P2 = (p.hp // DAMAGE for p in WARDEN.phases[:2])  # hits to clear each phase


class Fight:
    """Builds fight events by hand, with a fake clock."""

    def __init__(self, store: SqlEventStore, clock: FakeClock) -> None:
        self.store, self.clock = store, clock
        self.attempt: UUID | None = None

    def start(self, max_hp: int = 100, cost: int = 35, phases: int | None = 2) -> None:
        """An attempt at the Warden. Two phases by default, as attempts began before phase 3
        existed: the rule tests here are about the HP phases (phase 3 has tests of its own)."""
        self.clock.advance(seconds=1)
        event = FightStarted(self.clock.now(), WARDEN.id, 1, max_hp, cost, phases=phases)
        self.store.append(event)
        self.attempt = event.id

    def turn(
        self, correct: bool = True, times: int = 1, action: FightAction = FightAction.ANSWER
    ) -> None:
        assert self.attempt is not None
        for _ in range(times):
            self.clock.advance(seconds=1)
            self.store.append(FightTurn(self.clock.now(), self.attempt, action, correct))

    def record(self) -> BossRecord:
        today = CAL.day_of(self.clock.now())
        return replay(self.store.all(), CAL, today).bosses[WARDEN.id]


def live(fight: Fight) -> Attempt:
    current = fight.record().current
    assert current is not None
    return current


def last(record: BossRecord) -> Attempt:
    assert record.last is not None
    return record.last


@pytest.fixture
def fight(store: SqlEventStore, clock: FakeClock) -> Fight:
    return Fight(store, clock)


# --- questions ----------------------------------------------------------------


def test_questions_are_stable_per_seed_and_turn() -> None:
    first = question(WARDEN, 0, seed=42, turn=3, verbs=VERBS)
    assert first == question(WARDEN, 0, seed=42, turn=3, verbs=VERBS)
    assert first.kind is Kind.TE
    kinds = {question(WARDEN, 1, 42, turn, VERBS).kind for turn in range(4)}
    assert kinds == {Kind.REQUEST, Kind.SEQUENCE}


def test_a_full_width_comma_counts() -> None:
    q = Question(Kind.SEQUENCE, (Verb("起きる", "おきる"), Verb("食べる", "たべる")))
    assert q.accepts("おきて\uff0cたべる")


@pytest.mark.parametrize(
    ("q", "good", "bad"),
    [
        (Question(Kind.TE, (Verb("食べる", "たべる"),)), ["食べて", "たべて"], ["たべって"]),
        (
            Question(Kind.REQUEST, (Verb("待つ", "まつ"),)),
            ["待ってください", "まって下さい", "まって ください"],
            ["待って", "まちてください"],
        ),
        (
            Question(Kind.SEQUENCE, (Verb("起きる", "おきる"), Verb("食べる", "たべる"))),
            ["起きて、食べる", "おきてたべる", "起きて, たべる"],
            ["起きて、食べて", "食べて、起きる"],
        ),
    ],
)
def test_answers_accept_kana_kanji_and_punctuation(
    q: Question, good: list[str], bad: list[str]
) -> None:
    assert all(q.accepts(g) for g in good)
    assert not any(q.accepts(b) for b in bad)
    assert q.accepts(q.answers[0]) and q.accepts(q.answers[1])


# --- fight rules --------------------------------------------------------------


def test_hits_clear_phase_one_then_two_and_win(fight: Fight) -> None:
    fight.start()
    fight.turn(times=P1 - 1)
    assert live(fight).beat is Beat.HIT
    fight.turn()
    current = live(fight)
    assert (current.phase, current.beat, current.boss_hp) == (1, Beat.PHASE, WARDEN.phases[1].hp)
    fight.turn(times=P2)
    record = fight.record()
    assert record.defeated and last(record).outcome is Outcome.WON


def test_a_first_try_win_pays_the_bonus_and_lights_the_bonfire(
    fight: Fight, store: SqlEventStore, clock: FakeClock
) -> None:
    fight.start()
    fight.turn(times=P1 + P2)
    state = replay(store.all(), CAL, CAL.day_of(clock.now()))
    hits = (P1 + P2) * 5
    assert state.souls == hits + VICTORY_SOULS + 250
    assert state.lit_today
    assert state.jobs[Track.RONIN].xp == state.souls


def test_mistakes_cost_hp_and_three_kill(fight: Fight) -> None:
    fight.start()
    fight.turn(correct=False, times=2)
    assert live(fight).hp == 30
    fight.turn(correct=False)
    record = fight.record()
    assert record.current is None
    assert (last(record).outcome, last(record).beat, record.deaths) == (Outcome.DIED, Beat.DIED, 1)


def test_estus_heals_twice_per_attempt_and_refills_on_retry(fight: Fight) -> None:
    fight.start()
    fight.turn(action=FightAction.ESTUS)  # full HP: nothing happens
    assert live(fight).estus == 2
    fight.turn(correct=False)
    fight.turn(action=FightAction.ESTUS, times=3)
    current = live(fight)
    assert (current.hp, current.estus, current.can_drink) == (100, 1, False)
    fight.turn(correct=False, times=3)
    fight.start()
    assert live(fight).estus == 2


def test_wounds_and_cleared_phases_carry_over(fight: Fight) -> None:
    fight.start()
    fight.turn(times=P1)  # into phase 2
    fight.turn(correct=False, times=3)  # died there
    fight.start()
    current = live(fight)
    assert current.phase == 1
    assert current.wound == pytest.approx(0.9)
    assert current.boss_hp == round(WARDEN.phases[1].hp * 0.9)
    for _ in range(5):
        fight.turn(correct=False, times=3)
        fight.start()
    assert live(fight).wound == pytest.approx(0.7)


def test_a_loss_still_pays_for_every_hit(
    fight: Fight, store: SqlEventStore, clock: FakeClock
) -> None:
    fight.start()
    fight.turn(times=4)
    fight.turn(correct=False, times=3)
    state = replay(store.all(), CAL, CAL.day_of(clock.now()))
    assert state.souls == 20
    assert not state.lit_today


def test_a_later_win_has_no_first_try_bonus(
    fight: Fight, store: SqlEventStore, clock: FakeClock
) -> None:
    fight.start()
    fight.turn(correct=False, times=3)
    fight.start()
    fight.turn(times=P1 + P2)
    record = fight.record()
    assert last(record).number == 2
    assert sum(r.souls for r in record.rewards if r.lights) == VICTORY_SOULS


def test_turns_after_a_fight_ends_change_nothing(fight: Fight) -> None:
    fight.start()
    fight.turn(correct=False, times=3)
    fight.turn(times=5)
    assert last(fight.record()).hits == 0


def test_starting_over_a_live_fight_abandons_it(fight: Fight) -> None:
    fight.start()
    fight.turn(times=2)
    fight.start()
    record = fight.record()
    assert [a.outcome for a in record.attempts] == [Outcome.ABANDONED, Outcome.ACTIVE]
    assert live(fight).number == 1


def test_stray_events_are_ignored(store: SqlEventStore, clock: FakeClock) -> None:
    store.append(FightStarted(clock.now(), "no-such-boss", 1, 100, 35))
    store.append(FightTurn(clock.now(), UUID(int=1), FightAction.ANSWER, True))
    store.append(FightStarted(clock.now() + timedelta(days=3), WARDEN.id, 1, 100, 35))
    state = replay(store.all(), CAL, CAL.day_of(clock.now()))
    assert state.bosses[WARDEN.id].attempts == []


# --- service ------------------------------------------------------------------


def test_service_runs_a_whole_fight(store: SqlEventStore, clock: FakeClock) -> None:
    learn(store, clock)
    fights = FightService(store, clock, CAL)
    view = fights.enter(WARDEN.id)
    assert fights.enter(WARDEN.id).attempt == view.attempt  # resumes, never restarts
    while (attempt := view.record.current) is not None and not attempt.conversing:
        clock.advance(seconds=3)
        ask = view.question
        assert ask is not None
        view = fights.answer(WARDEN.id, str(attempt.id), attempt.turns, ask.answers[1])
        assert view.answered is not None and view.answered.correct
    while (attempt := view.record.current) is not None and not attempt.judging:  # phase 3
        clock.advance(seconds=3)
        assert isinstance(view.question, Question)
        line = view.question.answers[0] + "。"
        view = fights.reply(WARDEN.id, str(attempt.id), len(attempt.replies), line)
    assert attempt is not None and not view.record.defeated  # waits for the Sensei
    turns = [{"prompt": "…", "reply": r, "ok": True} for r in attempt.replies]
    AgentDesk(store, clock, CAL).submit(
        {"agent": "sensei", "task": verdict_task(attempt), "passed": True, "turns": turns}
    )
    view = fights.view(WARDEN.id)
    assert view.record.defeated
    assert view.state.lit_today


def test_service_refuses_stale_turns(store: SqlEventStore, clock: FakeClock) -> None:
    learn(store, clock)
    fights = FightService(store, clock, CAL)
    view = fights.enter(WARDEN.id)
    attempt = view.record.current
    assert attempt is not None
    clock.advance(seconds=3)
    fights.answer(WARDEN.id, str(attempt.id), 0, "x")
    clock.advance(seconds=3)
    again = fights.answer(WARDEN.id, str(attempt.id), 0, "x")  # double submit
    assert again.record.current is not None and again.record.current.turns == 1
    with pytest.raises(FightError, match="over"):
        fights.answer(WARDEN.id, "00000000-0000-0000-0000-000000000000", 1, "x")
    clock.advance(seconds=3)
    drunk = fights.drink(WARDEN.id, str(attempt.id)).record.current
    assert drunk is not None and drunk.estus == 1


def test_service_needs_enough_verbs(store: SqlEventStore, clock: FakeClock) -> None:
    fights = FightService(store, clock, CAL)
    with pytest.raises(FightError, match="6 verbs"):
        fights.enter(WARDEN.id)
    with pytest.raises(FightError, match="no boss"):
        fights.view("nope")


# --- page ---------------------------------------------------------------------


def fields(page: str) -> dict[str, str]:
    return dict(re.findall(r'<input type="hidden" name="(\w+)" value="([^"]*)">', page))


def test_fight_page_from_gate_to_death_to_retry(
    client: TestClient, store: SqlEventStore, clock: FakeClock
) -> None:
    learn(store, clock)
    gate = client.get("/boss/te-warden").text
    assert "Enter the fog" in gate
    page = client.post("/boss/te-warden/enter", headers=HX).text
    assert "Phase 1 of 3" in page and 'class="timer" data-seconds="20"' in page
    for _ in range(3):
        page = client.post(
            "/boss/te-warden/answer", data={**fields(page), "answer": "x"}, headers=HX
        ).text
    assert "YOU DIED" in page
    assert "10% less HP next time" in page
    page = client.post("/boss/te-warden/enter", headers=HX).text
    assert "wounded 10%" in page
    assert "Drink Estus (2)" in page


def test_fight_page_shows_hits_and_estus(
    client: TestClient, store: SqlEventStore, clock: FakeClock
) -> None:
    learn(store, clock)
    page = client.post("/boss/te-warden/enter", headers=HX).text
    page = client.post(
        "/boss/te-warden/answer", data={**fields(page), "answer": "x"}, headers=HX
    ).text
    assert "beat-miss" in page and "you wrote x" in page
    page = client.post(
        "/boss/te-warden/estus", data={"attempt": fields(page)["attempt"]}, headers=HX
    ).text
    assert "beat-estus" in page and "Drink Estus (1)" in page


def test_fight_pages_without_javascript_redirect(
    client: TestClient, store: SqlEventStore, clock: FakeClock
) -> None:
    learn(store, clock)
    response = client.post("/boss/te-warden/enter", follow_redirects=False)
    assert response.headers["location"] == "/boss/te-warden"
    assert "Phase 1 of 3" in client.get("/boss/te-warden").text  # a live fight resumes
    stale = client.post(
        "/boss/te-warden/answer",
        data={"attempt": "00000000-0000-0000-0000-000000000000", "turn": "0"},
        follow_redirects=False,
    )
    assert stale.status_code == 303
    assert (
        client.post(
            "/boss/te-warden/estus", data={"attempt": "x"}, follow_redirects=False
        ).status_code
        == 303
    )
    assert client.get("/boss/nope").status_code == 404


def test_the_gate_stays_shut_without_verbs(client: TestClient) -> None:
    assert "The fog will not part until you know 6 verbs." in client.get("/boss/te-warden").text
    assert client.post("/boss/te-warden/enter", headers=HX).status_code == 422
