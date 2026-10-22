from datetime import UTC, date, datetime, timedelta
from itertools import pairwise

import pytest

from hollow.adapters.db.store import SqlEventStore
from hollow.application.lessons import LessonError, LessonService, Status
from hollow.domain.activities import Track
from hollow.domain.conjugation import Ending, Verb
from hollow.domain.events import Event, LessonCompleted
from hollow.domain.lessons import INTERVALS, LESSONS, Run, souls_for_run, track
from hollow.domain.vocabulary import LearnedWord, to_event
from hollow.domain.world import replay
from tests.conftest import FakeClock
from tests.test_world import CAL, at, d, reviews

DECK_VERBS = [
    ("食べる", "たべる"), ("見る", "みる"), ("出る", "でる"), ("覚える", "おぼえる"),
    ("買う", "かう"), ("帰る", "かえる"), ("入る", "はいる"), ("言う", "いう"),
    ("飲む", "のむ"), ("読む", "よむ"), ("休む", "やすむ"),
    ("書く", "かく"), ("行く", "いく"), ("聞く", "きく"),
    ("話す", "はなす"), ("出す", "だす"),
    ("来る", "くる"),
]  # fmt: skip


def run(day: date, correct: int, total: int = 10, lesson: str = "te-ru") -> LessonCompleted:
    return LessonCompleted(at(day), lesson, correct, total)


def learn(store: SqlEventStore, clock: FakeClock, verbs: list[tuple[str, str]]) -> None:
    for n, (written, kana) in enumerate(verbs):
        store.append(to_event(LearnedWord(n, written, kana, "", "Verb"), clock.now()))


# --- lesson building ----------------------------------------------------------


def verbs() -> list[Verb]:
    return [Verb(w, k) for w, k in DECK_VERBS] + [Verb("する", "する")]


def test_each_lesson_drills_one_ending_group() -> None:
    pool = LESSONS["te-tsu"].pool(verbs())
    assert {v.written for v in pool} == {"買う", "帰る", "入る", "言う"}
    assert all(v.ending is Ending.TSU for v in pool)
    assert LESSONS["te-irregular"].available(verbs())  # 来る plus する


def test_questions_cycle_the_pool_without_back_to_back_repeats() -> None:
    spec = LESSONS["te-shite"]
    questions = spec.questions(verbs(), seed=7)
    assert len(questions) == 5  # small pools still make a 5-question lesson
    assert all(a != b for a, b in pairwise(questions))
    assert spec.questions(verbs(), seed=7) == questions
    assert len(LESSONS["te-mixed"].questions(verbs(), seed=1)) == 12


def test_a_group_with_too_few_verbs_is_locked() -> None:
    assert not LESSONS["te-nde"].available([Verb("飲む", "のむ")])


# --- rewards and refreshers ---------------------------------------------------


def test_first_clear_pays_full_then_practice_pays_a_quarter() -> None:
    outcomes, progress = track([run(d(0), 9), run(d(0), 10)], CAL, today=d(0))
    assert [(o.run, o.souls) for o in outcomes] == [(Run.FIRST, 45), (Run.PRACTICE, 12)]
    assert progress["te-ru"].due_on == d(1)


def test_refreshers_follow_the_schedule() -> None:
    events: list[Event] = [run(d(0), 10), run(d(1), 10), run(d(4), 8), run(d(7), 10)]
    outcomes, progress = track(events, CAL, today=d(7))
    assert [o.run for o in outcomes] == [Run.FIRST, Run.REFRESHER, Run.REFRESHER, Run.REFRESHER]
    assert outcomes[1].souls == souls_for_run(Run.REFRESHER, 10) == 30
    # 1 day, then 3; an 80% refresher repeats 3 days; a perfect one moves on to 7
    assert progress["te-ru"].step == 2
    assert progress["te-ru"].due_on == d(7) + timedelta(days=INTERVALS[2])


def test_a_failed_attempt_still_pays_but_does_not_clear() -> None:
    outcomes, progress = track([run(d(0), 5)], CAL, today=d(0))
    assert (outcomes[0].souls, outcomes[0].passed) == (25, False)
    assert not progress["te-ru"].cleared
    assert progress["te-ru"].run_on(d(0)) is Run.FIRST


def test_a_failed_refresher_stays_due() -> None:
    _, progress = track([run(d(0), 10), run(d(1), 3)], CAL, today=d(2))
    assert progress["te-ru"].is_due(d(2))


def test_future_runs_are_ignored() -> None:
    outcomes, _ = track([run(d(3), 10)], CAL, today=d(0))
    assert outcomes == []


def test_clearing_a_lesson_lights_the_bonfire_and_feeds_the_ronin() -> None:
    state = replay([run(d(0), 8)], CAL, today=d(0))
    assert state.lit_today
    assert state.souls == 40
    assert state.jobs[Track.RONIN].xp == 40
    assert [o.souls for o in state.today_lessons] == [40]


def test_practice_and_failed_runs_do_not_light_the_bonfire() -> None:
    assert not replay([run(d(0), 7)], CAL, today=d(0)).lit_today
    # cleared on d0, refresher on d1 (next due d4), so d2's run is practice
    events: list[Event] = [run(d(0), 10), run(d(1), 10), run(d(2), 10)]
    state = replay(events, CAL, today=d(2))
    assert [o.run for o in state.today_lessons] == [Run.PRACTICE]
    assert not state.lit_today
    assert replay([*events, reviews(d(2))], CAL, today=d(2)).lit_today


def test_lessons_due_counts_refreshers_waiting_today() -> None:
    assert replay([run(d(0), 10)], CAL, today=d(1)).lessons_due == 1


# --- service ------------------------------------------------------------------


def test_overview_shows_which_lessons_you_can_take(store: SqlEventStore, clock: FakeClock) -> None:
    learn(store, clock, DECK_VERBS[:4])  # four る-verbs only
    cards = {c.spec.id: c for c in LessonService(store, clock, CAL).overview()}
    assert cards["te-ru"].status is Status.NEW
    assert cards["te-ru"].verbs == 4
    assert cards["te-nde"].status is Status.LOCKED


def test_a_run_is_graded_on_the_server_and_recorded_once(
    store: SqlEventStore, clock: FakeClock
) -> None:
    learn(store, clock, DECK_VERBS)
    service = LessonService(store, clock, CAL)
    started = service.start("te-ru")
    written = [q.written for q in started.questions]
    resumed = service.resume("te-ru", str(started.id), written)
    answers = [q.te_form.kana for q in resumed.questions]
    answers[0] = "まちがい"

    outcome, state = service.finish(resumed, answers)
    assert (outcome.correct, outcome.total, outcome.run) == (4, 5, Run.FIRST)
    assert outcome.passed and state.lit_today

    again, _ = service.finish(resumed, answers)  # a resubmitted finish
    assert again == outcome
    assert len([e for e in store.all() if isinstance(e, LessonCompleted)]) == 1
    cards = {c.spec.id: c for c in service.overview()}
    assert cards["te-ru"].status is Status.WAITING


def test_due_lessons_show_as_due(store: SqlEventStore, clock: FakeClock) -> None:
    learn(store, clock, DECK_VERBS)
    store.append(LessonCompleted(clock.now() - timedelta(days=1), "te-ru", 5, 5))
    cards = {c.spec.id: c for c in LessonService(store, clock, CAL).overview()}
    assert cards["te-ru"].status is Status.DUE


@pytest.mark.parametrize(
    ("lesson", "run_id", "written", "message"),
    [
        ("nope", "x", [], "no lesson called nope"),
        ("te-ru", "not-a-uuid", ["食べる"], "does not match"),
        ("te-ru", "00000000-0000-0000-0000-000000000000", ["書く"], "does not match"),
        ("te-ru", "00000000-0000-0000-0000-000000000000", [], "wrong number"),
    ],
)
def test_tampered_runs_are_refused(
    store: SqlEventStore,
    clock: FakeClock,
    lesson: str,
    run_id: str,
    written: list[str],
    message: str,
) -> None:
    learn(store, clock, DECK_VERBS)
    with pytest.raises(LessonError, match=message):
        LessonService(store, clock, CAL).resume(lesson, run_id, written)


def test_locked_lessons_cannot_start_and_runs_need_every_answer(
    store: SqlEventStore, clock: FakeClock
) -> None:
    service = LessonService(store, clock, CAL)
    with pytest.raises(LessonError, match="needs 2 learned verbs"):
        service.start("te-ru")
    learn(store, clock, DECK_VERBS)
    started = service.start("te-ru")
    with pytest.raises(LessonError, match="Answer every question"):
        service.finish(started, [])


def test_lesson_runs_round_trip_through_the_store(store: SqlEventStore) -> None:
    event = LessonCompleted(datetime(2026, 10, 23, 9, tzinfo=UTC), "te-ru", 7, 10)
    store.append(event)
    assert store.all() == [event]
    with pytest.raises(ValueError, match="between"):
        LessonCompleted(event.occurred_at, "te-ru", 11, 10)
    with pytest.raises(ValueError, match="timezone"):
        LessonCompleted(datetime(2026, 10, 23), "te-ru", 1, 10)
