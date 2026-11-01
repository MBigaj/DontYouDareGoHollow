"""Undead Village, part 3: the Plain-Form Gargoyle."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from hollow.adapters.db.store import SqlEventStore
from hollow.application.agents import AgentDesk
from hollow.application.fights import FightError, FightService
from hollow.application.lessons import LessonService
from hollow.domain.armory import BOSS_ARMOUR, BOSS_WEAPONS, WEAPONS, boss_loot
from hollow.domain.bosses import (
    GARGOYLE,
    PLAIN_RUBRIC,
    SOULS_PER_HIT,
    Attempt,
    Kind,
    Question,
    lines,
    question,
    rubric,
    spoken,
    verdict_task,
)
from hollow.domain.conjugation import Form, Verb
from hollow.domain.events import ArmourBought, ArmourEquipped, FightStarted
from hollow.domain.world import WorldState, replay
from tests.conftest import FakeClock
from tests.test_armory import fell_the_warden
from tests.test_web_lessons import learn
from tests.test_world import CAL

HX = {"HX-Request": "true"}
VERBS = [Verb("読む", "よむ", "to read"), Verb("食べる", "たべる", "to eat"), Verb("ある", "ある")]


def state(store: SqlEventStore, clock: FakeClock) -> WorldState:
    return replay(store.all(), CAL, CAL.day_of(clock.now()))


def clear_village(store: SqlEventStore, clock: FakeClock, count: int = 3) -> None:
    """Fells the Warden, then clears `count` Undead Village lessons."""
    learn(store, clock)
    fell_the_warden(store, clock)
    service = LessonService(store, clock, CAL)
    for lesson_id in ("pf-ta", "pf-nai-ru", "pf-nai-u", "pf-nakatta")[:count]:
        clock.advance(seconds=5)
        run = service.start(lesson_id)
        answers = [run.spec.answer(n, v).kana for n, v in enumerate(run.questions)]
        service.finish(run, answers, roll=0.99)


def current(store: SqlEventStore, clock: FakeClock) -> Attempt:
    attempt = state(store, clock).bosses[GARGOYLE.id].current
    assert attempt is not None
    return attempt


# --- the boss -------------------------------------------------------------------


def test_the_gargoyle_is_data() -> None:
    assert (GARGOYLE.recommended, GARGOYLE.home, GARGOYLE.node) == (
        4, "/map/undead-village", "gargoyle",
    )  # fmt: skip
    assert [p.forms for p in GARGOYLE.phases[:2]] == [
        (Form.TA, Form.NAI), (Form.NAKATTA, Form.TEIRU, Form.TA, Form.NAI),
    ]  # fmt: skip
    third = GARGOYLE.phases[2]
    assert third.conversation and third.prompts == 4 and rubric(GARGOYLE, 2) == PLAIN_RUBRIC
    assert BOSS_WEAPONS[GARGOYLE.id] == "gargoyle-halberd"
    assert BOSS_ARMOUR[GARGOYLE.id] == "gargoyle-helm"
    assert WEAPONS["gargoyle-halberd"].damage(4, GARGOYLE.recommended) == 15
    assert boss_loot(GARGOYLE.id) == [
        "Gargoyle's Tail Halberd", "Gargoyle Helm", "4 Large Titanite Shards", "2 Titanite Chunks",
    ]  # fmt: skip


def test_plain_questions_ask_their_form() -> None:
    asked = [question(GARGOYLE, 1, 3, n, VERBS) for n in range(8)]
    assert all(isinstance(q, Question) and q.kind is Kind.PLAIN for q in asked)
    assert [q.form for q in asked if isinstance(q, Question)][:4] == [
        Form.NAKATTA, Form.TEIRU, Form.TA, Form.NAI,
    ]  # fmt: skip
    teiru = [q for q in asked if isinstance(q, Question) and q.form is Form.TEIRU]
    assert all(q.verbs[0].written != "ある" for q in teiru)
    q = Question(Kind.PLAIN, (VERBS[0],), Form.NAKATTA)
    assert q.answers == ("読まなかった", "よまなかった")
    assert q.accepts("よまなかった") and not q.accepts("読まない")


def test_his_lines_are_plain_style() -> None:
    line = Question(Kind.PLAIN, (Verb("食べる", "たべる", "to eat"),), Form.TA)
    assert spoken(line) == (
        "Tell me something you did yesterday, with eat (食べる). Plain style, no 〜ます."
    )
    assert "〜ます" in PLAIN_RUBRIC and "〜なかった" in PLAIN_RUBRIC


# --- the gate -------------------------------------------------------------------


def test_the_fog_parts_after_three_village_lessons(store: SqlEventStore, clock: FakeClock) -> None:
    clear_village(store, clock, count=2)
    fights = FightService(store, clock, CAL)
    assert not fights.ready(GARGOYLE.id)
    assert fights.requirement(GARGOYLE.id) == (
        "The fog will not part until you clear 3 Undead Village lessons (2 so far)."
    )
    with pytest.raises(FightError, match="clear 3 Undead Village lessons"):
        fights.enter(GARGOYLE.id)
    clear_village_more(store, clock)
    assert fights.ready(GARGOYLE.id)


def clear_village_more(store: SqlEventStore, clock: FakeClock) -> None:
    service = LessonService(store, clock, CAL)
    clock.advance(seconds=5)
    run = service.start("pf-nakatta")
    service.finish(run, [run.spec.answer(n, v).kana for n, v in enumerate(run.questions)], 0.99)


# --- the fight ------------------------------------------------------------------


def test_a_whole_fight_through_his_question(store: SqlEventStore, clock: FakeClock) -> None:
    clear_village(store, clock)
    fights = FightService(store, clock, CAL)
    view = fights.enter(GARGOYLE.id)
    while (attempt := view.record.current) is not None and not attempt.conversing:
        clock.advance(seconds=2)
        assert view.question is not None
        view = fights.answer(GARGOYLE.id, str(attempt.id), attempt.turns, view.question.answers[1])
        assert view.answered is not None and view.answered.correct
    attempt = current(store, clock)
    assert attempt.phase == 2 and attempt.prompts == 4
    said = lines(GARGOYLE, attempt, fights.verbs())
    assert [q.form for q in said] == [Form.TA, Form.NAI, Form.TEIRU, Form.NAKATTA]
    for line in said:
        clock.advance(seconds=2)
        now = current(store, clock)
        fights.reply(GARGOYLE.id, str(now.id), len(now.replies), line.answers[0] + "。")
    judging = current(store, clock)
    task = next(
        t for t in AgentDesk(store, clock, CAL).inbox()["tasks"] if t["task"].startswith("boss:")
    )
    assert task["rubric"] == PLAIN_RUBRIC and "Plain style" in task["transcript"][0]["line"]
    turns: list[dict[str, Any]] = [{"prompt": "…", "reply": r, "ok": True} for r in judging.replies]
    AgentDesk(store, clock, CAL).submit(
        {"agent": "sensei", "task": verdict_task(judging), "passed": True, "turns": turns}
    )
    world = state(store, clock)
    assert world.bosses[GARGOYLE.id].defeated
    assert world.armory.owns("gargoyle-halberd") and world.armory.owns_armour("gargoyle-helm")


def test_the_helm_raises_what_each_right_answer_pays(
    store: SqlEventStore, clock: FakeClock
) -> None:
    clear_village(store, clock)
    clock.advance(seconds=1)
    store.append(ArmourBought(clock.now(), "gargoyle-helm", 0))
    clock.advance(seconds=1)
    store.append(ArmourEquipped(clock.now(), "gargoyle-helm"))
    view = FightService(store, clock, CAL).enter(GARGOYLE.id)
    assert view.attempt is not None and view.attempt.souls_per_hit == SOULS_PER_HIT + 2
    started = next(e for e in reversed(list(store.all())) if isinstance(e, FightStarted))
    assert started.souls_per_hit == 7
    assert list(store.all())[-1] == started  # round-trips through the store


# --- the pages ------------------------------------------------------------------


def test_the_gate_on_the_village_map_and_the_fight_page(
    client: TestClient, store: SqlEventStore, clock: FakeClock
) -> None:
    clear_village(store, clock, count=2)
    page = client.get("/map/undead-village").text
    assert "It will not part until you clear 3 Undead Village lessons (2 so far)." in page
    clear_village_more(store, clock)
    page = client.get("/map/undead-village").text
    assert 'href="/boss/pf-gargoyle"' in page and "Enter the fog" in page
    gate = client.get("/boss/pf-gargoyle").text
    assert "The Plain-Form Gargoyle" in gate and "arena_undead_village.png" in gate
    fight = client.post("/boss/pf-gargoyle/enter", headers=HX).text
    assert "Phase 1 of 3" in fight and "gargoyle_body.png" in fight
    assert "〜た (plain past)" in fight and 'data-seconds="20"' in fight
