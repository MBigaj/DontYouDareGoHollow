from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from hollow.domain.activities import ActivityKind, lights_bonfire, souls_for
from hollow.domain.calendar import GameCalendar
from hollow.domain.events import Event, MessageLeft, StudyLogged
from hollow.domain.world import MAX_HOLLOWING, replay

WARSAW = ZoneInfo("Europe/Warsaw")
CAL = GameCalendar(WARSAW, day_start_hour=4)
DAY1 = date(2026, 10, 1)


def at(day: date, hour: int = 12) -> datetime:
    return datetime(day.year, day.month, day.day, hour, tzinfo=WARSAW)


def reviews(day: date, n: int = 10, hour: int = 12) -> StudyLogged:
    return StudyLogged(at(day, hour), ActivityKind.ANKI_REVIEWS, n)


def d(offset: int) -> date:
    return DAY1 + timedelta(days=offset)


# --- activities ---------------------------------------------------------------


def test_souls_follow_the_rate_table() -> None:
    assert souls_for(ActivityKind.ANKI_REVIEWS, 10) == 20
    assert souls_for(ActivityKind.DEV_STUDY, 15) == 30
    assert souls_for(ActivityKind.PULL_REQUEST, 1) == 100


def test_kindling_needs_one_activity_to_reach_its_threshold() -> None:
    assert lights_bonfire({ActivityKind.ANKI_REVIEWS: 10})
    assert lights_bonfire({ActivityKind.DEV_STUDY: 5})
    assert not lights_bonfire({ActivityKind.ANKI_REVIEWS: 9, ActivityKind.DEV_STUDY: 4})
    assert not lights_bonfire({})


# --- events and calendar ------------------------------------------------------


def test_events_reject_bad_input() -> None:
    with pytest.raises(ValueError):
        StudyLogged(at(DAY1), ActivityKind.ANKI_REVIEWS, 0)
    with pytest.raises(ValueError):
        StudyLogged(datetime(2026, 10, 1, 12), ActivityKind.ANKI_REVIEWS, 1)
    with pytest.raises(ValueError):
        MessageLeft(at(DAY1), "   ")
    with pytest.raises(ValueError):
        MessageLeft(datetime(2026, 10, 1, 12), "hi")


def test_late_night_study_counts_for_the_previous_day() -> None:
    assert CAL.day_of(at(d(1), hour=3)) == DAY1
    assert CAL.day_of(at(d(1), hour=4)) == d(1)
    assert CAL.day_of(datetime(2026, 10, 1, 22, 30, tzinfo=UTC)) == DAY1  # 00:30 Warsaw


def test_calendar_rejects_bad_hour() -> None:
    with pytest.raises(ValueError):
        GameCalendar(WARSAW, day_start_hour=24)


# --- replay -------------------------------------------------------------------


def test_empty_log_is_a_fresh_human() -> None:
    state = replay([], CAL, today=DAY1)
    assert (state.souls, state.hollowing, state.streak, state.deaths) == (0, 0, 0, 0)
    assert state.status == "Human"
    assert not state.lit_today
    assert state.bloodstain is None


def test_lighting_today_earns_souls_and_a_streak() -> None:
    state = replay([reviews(DAY1)], CAL, today=DAY1)
    assert state.lit_today
    assert state.souls == 20
    assert state.streak == 1
    assert state.bonfires_lit == 1


def test_today_is_never_a_death_even_below_kindling() -> None:
    state = replay([reviews(DAY1, n=3)], CAL, today=DAY1)
    assert not state.lit_today
    assert state.souls == 6
    assert state.deaths == 0


def test_missed_day_drops_souls_as_bloodstain() -> None:
    state = replay([reviews(d(0))], CAL, today=d(2))
    assert state.souls == 0
    assert state.bloodstain is not None
    assert state.bloodstain.souls == 20
    assert state.bloodstain.dropped_on == d(1)
    assert state.deaths == 1
    assert state.hollowing == 1
    assert state.status == "Fading"


def test_lighting_the_next_day_recovers_the_bloodstain() -> None:
    state = replay([reviews(d(0)), reviews(d(2))], CAL, today=d(2))
    assert state.bloodstain is None
    assert state.souls == 40
    assert state.hollowing == 0
    assert state.souls_lost == 0


def test_second_missed_day_loses_the_bloodstain() -> None:
    state = replay([reviews(d(0)), reviews(d(3))], CAL, today=d(3))
    assert state.souls == 20  # only today's souls
    assert state.souls_lost == 20
    assert state.deaths == 2
    assert state.bloodstain is None


def test_souls_earned_on_a_missed_day_drop_with_a_new_bloodstain() -> None:
    events: list[Event] = [reviews(d(0)), reviews(d(1), n=4)]
    state = replay(events, CAL, today=d(3))
    # day 1 (4 reviews) is a death: 20 + 8 drop. Day 2 is another death: that stain is lost.
    assert state.souls_lost == 28
    assert state.bloodstain is None


def test_bloodstain_from_partial_day_is_recoverable() -> None:
    events: list[Event] = [reviews(d(0)), reviews(d(1), n=4), reviews(d(2))]
    state = replay(events, CAL, today=d(2))
    assert state.souls == 20 + 8 + 20
    assert state.souls_lost == 0


def test_hollowing_caps_and_recovers_one_step_per_lit_day() -> None:
    state = replay([reviews(d(0))], CAL, today=d(9))
    assert state.hollowing == MAX_HOLLOWING
    assert state.status == "Hollow"

    events: list[Event] = [reviews(d(0)), reviews(d(9)), reviews(d(10)), reviews(d(11))]
    state = replay(events, CAL, today=d(11))
    assert state.hollowing == MAX_HOLLOWING - 3
    assert state.status == "Fading"


def test_hollowing_status_bands() -> None:
    assert replay([reviews(d(0))], CAL, today=d(4)).status == "Hollowing"


def test_streak_survives_while_today_is_still_open() -> None:
    events: list[Event] = [reviews(d(0)), reviews(d(1)), reviews(d(2))]
    assert replay(events, CAL, today=d(3)).streak == 3
    assert replay([*events, reviews(d(3))], CAL, today=d(3)).streak == 4
    assert replay(events, CAL, today=d(4)).streak == 0


def test_recent_days_are_newest_first() -> None:
    state = replay([reviews(d(0)), reviews(d(2))], CAL, today=d(2))
    assert [s.day for s in state.recent_days] == [d(2), d(1), d(0)]
    assert [s.died for s in state.recent_days] == [False, True, False]


def test_future_events_are_ignored() -> None:
    state = replay([reviews(d(0)), reviews(d(5))], CAL, today=d(0))
    assert state.souls == 20


def test_today_totals_sum_per_activity() -> None:
    events: list[Event] = [
        reviews(d(0), n=6),
        reviews(d(0), n=6, hour=20),
        StudyLogged(at(d(0)), ActivityKind.DEV_STUDY, 30),
    ]
    state = replay(events, CAL, today=d(0))
    assert state.today_totals == {ActivityKind.ANKI_REVIEWS: 12, ActivityKind.DEV_STUDY: 30}
    assert state.lit_today


def test_message_shows_the_newest_one_from_a_past_day() -> None:
    events: list[Event] = [
        MessageLeft(at(d(0), 9), "older"),
        MessageLeft(at(d(1), 21), "Try て-form ahead"),
        MessageLeft(at(d(2), 10), "written today, shown tomorrow"),
    ]
    state = replay(events, CAL, today=d(2))
    assert state.message is not None
    assert state.message.text == "Try て-form ahead"
    assert state.message.left_on == d(1)
