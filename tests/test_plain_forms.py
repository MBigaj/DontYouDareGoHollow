"""Undead Village, part 1: the plain forms and their lessons, sealed until the Warden falls."""

import re

import pytest
from fastapi.testclient import TestClient

from hollow.adapters.db.store import SqlEventStore
from hollow.adapters.web.app import hint
from hollow.application.agents import AgentDesk, AgentError
from hollow.application.lessons import LessonError, LessonService, Status
from hollow.domain.conjugation import Ending, Form, Verb
from hollow.domain.lessons import LESSONS, REGION_GATES, region_open
from hollow.domain.vocabulary import LearnedWord, to_event
from tests.conftest import FakeClock
from tests.test_agents import quests
from tests.test_armory import fell_the_warden
from tests.test_lessons import DECK_VERBS
from tests.test_web_lessons import hidden, learn
from tests.test_world import CAL

VILLAGE = [s for s in LESSONS.values() if s.region == "undead-village"]

# --- conjugation ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("written", "kana", "forms"),
    [
        ("食べる", "たべる", ("食べている", "食べた", "食べない", "食べなかった")),
        ("書く", "かく", ("書いている", "書いた", "書かない", "書かなかった")),
        ("泳ぐ", "およぐ", ("泳いでいる", "泳いだ", "泳がない", "泳がなかった")),
        ("話す", "はなす", ("話している", "話した", "話さない", "話さなかった")),
        ("待つ", "まつ", ("待っている", "待った", "待たない", "待たなかった")),
        ("死ぬ", "しぬ", ("死んでいる", "死んだ", "死なない", "死ななかった")),
        ("遊ぶ", "あそぶ", ("遊んでいる", "遊んだ", "遊ばない", "遊ばなかった")),
        ("読む", "よむ", ("読んでいる", "読んだ", "読まない", "読まなかった")),
        ("買う", "かう", ("買っている", "買った", "買わない", "買わなかった")),
        ("帰る", "かえる", ("帰っている", "帰った", "帰らない", "帰らなかった")),
        ("行く", "いく", ("行っている", "行った", "行かない", "行かなかった")),
        ("する", "する", ("している", "した", "しない", "しなかった")),
        (
            "勉強する",
            "べんきょうする",
            ("勉強している", "勉強した", "勉強しない", "勉強しなかった"),
        ),
        ("来る", "くる", ("来ている", "来た", "来ない", "来なかった")),
    ],
)
def test_plain_forms(written: str, kana: str, forms: tuple[str, str, str, str]) -> None:
    verb = Verb(written, kana)
    asked = (Form.TEIRU, Form.TA, Form.NAI, Form.NAKATTA)
    assert tuple(verb.form(f).written for f in asked) == forms
    assert verb.form(Form.TE) == verb.te_form


def test_kana_answers_and_the_exceptions() -> None:
    assert Verb("来る", "くる").form(Form.NAI).kana == "こない"
    assert Verb("来る", "くる").form(Form.TA).kana == "きた"
    assert Verb("ある", "ある").form(Form.NAI).written == "ない"
    assert Verb("ある", "ある").form(Form.NAKATTA).written == "なかった"
    assert Verb("会う", "あう").form(Form.NAI).accepts("あわない")
    assert not Verb("会う", "あう").form(Form.NAI).accepts("あない")


def test_every_deck_verb_conjugates() -> None:
    for written, kana in DECK_VERBS:
        for form in Form:
            assert Verb(written, kana).form(form).written.startswith(written[0])


# --- the lessons ----------------------------------------------------------------


def test_the_village_drills_each_plain_form() -> None:
    assert [s.id for s in VILLAGE] == [
        "pf-teiru", "pf-ta", "pf-nai-ru", "pf-nai-u", "pf-nakatta", "pf-mixed",
    ]  # fmt: skip
    asked = {f for s in VILLAGE for f in s.forms}
    assert asked == {Form.TEIRU, Form.TA, Form.NAI, Form.NAKATTA}
    assert all(s.forms == (Form.TE,) and s.region == "firelink" for s in LESSONS.values()
               if s not in VILLAGE)  # fmt: skip
    assert REGION_GATES == {"undead-village": "te-warden"}


def test_pools_follow_the_form() -> None:
    verbs = [Verb(w, k) for w, k in DECK_VERBS] + [Verb("ある", "ある"), Verb("する", "する")]
    teiru = LESSONS["pf-teiru"].pool(verbs)
    assert "ある" not in {v.written for v in teiru} and len(teiru) == len(verbs) - 1
    assert {v.ending for v in LESSONS["pf-nai-ru"].pool(verbs)} == {
        Ending.RU_VERB, Ending.IRREGULAR,
    }  # fmt: skip
    assert Ending.RU_VERB not in {v.ending for v in LESSONS["pf-nai-u"].pool(verbs)}


def test_the_mixed_lesson_asks_each_form_in_turn() -> None:
    spec = LESSONS["pf-mixed"]
    verb = Verb("飲む", "のむ")
    assert [spec.form_at(n) for n in range(5)] == [
        Form.TA, Form.NAI, Form.NAKATTA, Form.TEIRU, Form.TA,
    ]  # fmt: skip
    answers = ["飲んだ", "のまない", "飲まなかった", "飲んでいる"]
    assert spec.grade([verb] * 4, answers) == [True] * 4
    assert spec.grade([verb] * 4, ["飲んで"] * 4) == [False] * 4
    assert spec.asks(1) == "〜ない (plain negative)"


def test_region_gates() -> None:
    assert region_open("firelink", set())
    assert not region_open("undead-village", set())
    assert region_open("undead-village", {"te-warden"})


# --- the seal -------------------------------------------------------------------


def test_the_village_is_sealed_until_the_warden_falls(
    store: SqlEventStore, clock: FakeClock
) -> None:
    learn(store, clock)
    service = LessonService(store, clock, CAL)
    cards = {c.spec.id: c for c in service.overview()}
    assert cards["te-ru"].status is Status.NEW and not cards["te-ru"].sealed
    assert all(cards[s.id].sealed and cards[s.id].status is Status.LOCKED for s in VILLAGE)
    with pytest.raises(LessonError, match="Undead Village opens when The て-form Warden falls"):
        service.start("pf-ta")
    fell_the_warden(store, clock)
    cards = {c.spec.id: c for c in service.overview()}
    assert all(not cards[s.id].sealed and cards[s.id].status is Status.NEW for s in VILLAGE)
    run = service.start("pf-nai-u")
    answers = [run.spec.answer(n, v).kana for n, v in enumerate(run.questions)]
    outcome, _, state = service.finish(run, answers, roll=0.99)
    assert outcome.correct == outcome.total and state.lessons["pf-nai-u"].cleared
    assert state.lit_today


def test_hints_explain_the_form_asked() -> None:
    assert hint(Verb("読む", "よむ"), Form.TA) == (
        "Built like the て-form, with て → た and で → だ: 読んで → 読んだ."
    )
    assert "わ" in hint(Verb("買う", "かう"), Form.NAI)
    assert "ら" in hint(Verb("帰る", "かえる"), Form.NAI)
    assert (
        hint(Verb("食べる", "たべる"), Form.NAKATTA)
        == "〜ない with い → かった: 食べない → 食べなかった."
    )
    assert hint(Verb("来る", "くる"), Form.NAI).startswith("Irregular")
    assert hint(Verb("ある", "ある"), Form.NAI).startswith("ある is the exception")


# --- the pages ------------------------------------------------------------------


def test_the_lessons_page_groups_by_region(
    client: TestClient, store: SqlEventStore, clock: FakeClock
) -> None:
    learn(store, clock)
    page = client.get("/lessons").text  # only what you can play: the village stays off the page
    assert "Region 1 · Firelink Shrine" in page and "Region 2 · Undead Village" not in page
    assert 'href="/lessons/pf-' not in page
    assert "6 more lessons open later: fell The て-form Warden for Undead Village." in page
    sealed = client.get("/lessons/pf-ta").text
    assert "Undead Village opens when The て-form Warden falls." in sealed
    fell_the_warden(store, clock)
    page = client.get("/lessons").text
    assert "Region 2 · Undead Village" in page and 'href="/lessons/pf-ta"' in page
    assert "more lessons open later" not in page


def test_lessons_short_of_verbs_stay_off_the_page(
    client: TestClient, store: SqlEventStore, clock: FakeClock
) -> None:
    store.append(to_event(LearnedWord(0, "食べる", "たべる", "to eat", "Verb"), clock.now()))
    store.append(to_event(LearnedWord(1, "見る", "みる", "to see", "Verb"), clock.now()))
    page = client.get("/lessons").text
    assert 'href="/lessons/te-ru"' in page and 'href="/lessons/te-tsu"' not in page
    assert "more lessons open later: learn verbs in Anki" in page


def test_a_plain_form_lesson_asks_and_corrects_its_form(
    client: TestClient, store: SqlEventStore, clock: FakeClock
) -> None:
    learn(store, clock)
    fell_the_warden(store, clock)
    page = client.get("/lessons/pf-nakatta").text
    assert "〜なかった (plain past negative)" in page
    fields = hidden(page)
    deck = {w: Verb(w, k) for w, k in [*DECK_VERBS, ("する", "する")]}  # する is always known
    first = deck[fields["q"][0]]
    feedback = client.post(
        "/lessons/pf-nakatta/answer",
        data={"run": fields["run"][0], "q": fields["q"], "answer": "x"},
        headers={"HX-Request": "true"},
    ).text
    assert first.form(Form.NAKATTA).written in feedback
    assert "〜ない with い → かった" in feedback
    assert re.search(r"You wrote <span lang=\"ja\">x</span>", feedback)


# --- the agents -----------------------------------------------------------------


def test_the_quest_master_cannot_set_a_sealed_lesson(
    store: SqlEventStore, clock: FakeClock
) -> None:
    desk = AgentDesk(store, clock, CAL)
    lessons = {lesson["id"]: lesson for lesson in desk.inbox()["context"]["lessons"]}
    assert lessons["pf-ta"]["region"] == "undead-village" and not lessons["pf-ta"]["open"]
    assert lessons["te-ru"]["open"]
    sealed = quests()
    sealed["quests"][0]["check"]["lesson_id"] = "pf-ta"
    with pytest.raises(AgentError, match="pf-ta is sealed"):
        desk.submit(sealed)
