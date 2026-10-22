from datetime import date

import pytest
from fastapi.testclient import TestClient

from hollow.adapters.db.store import SqlEventStore
from hollow.application.bonfire import BonfireService, CannotLevelUp
from hollow.domain.activities import ActivityKind, Track
from hollow.domain.events import Event, StatLevelled, StudyLogged
from hollow.domain.progression import (
    STAT_MAX,
    Stat,
    job_progress,
    level_cost,
    max_hp,
    mistake_cost,
)
from hollow.domain.world import replay
from tests.conftest import FakeClock
from tests.test_world import CAL, at, d, reviews

HX = {"HX-Request": "true"}


def study(day: date, kind: ActivityKind, n: int) -> StudyLogged:
    return StudyLogged(at(day), kind, n)


def bought(day: date, stat: Stat, cost: int, hour: int = 13) -> StatLevelled:
    return StatLevelled(at(day, hour), stat, cost)


# --- rules --------------------------------------------------------------------


def test_each_level_bought_costs_more() -> None:
    assert [level_cost(sl) for sl in (0, 1, 11)] == [200, 240, 640]


def test_vigor_and_endurance_soften_boss_fights() -> None:
    assert (max_hp(1), max_hp(4)) == (100, 130)
    assert (mistake_cost(1), mistake_cost(3), mistake_cost(60)) == (35, 33, 20)


def test_jobs_need_100_xp_per_level_more_each_time() -> None:
    assert job_progress(Track.RONIN, 0).level == 1
    assert job_progress(Track.RONIN, 99).level == 1
    progress = job_progress(Track.RONIN, 420)  # 100 for Lv 2, 200 for Lv 3, then 120 more
    assert (progress.level, progress.into_level, progress.needed, progress.percent) == (
        3,
        120,
        300,
        40,
    )


# --- replay -------------------------------------------------------------------


def test_a_fresh_character_starts_at_level_one_everywhere() -> None:
    state = replay([], CAL, today=d(0))
    assert state.stats == dict.fromkeys(Stat, 1)
    assert (state.soul_level, state.character_level, state.level_cost) == (0, 2, 200)
    assert (state.max_hp, state.mistake_cost, state.effigies) == (100, 35, 2)


def test_jobs_level_from_souls_earned_per_track() -> None:
    events: list[Event] = [
        study(d(0), ActivityKind.ANKI_NEW_CARDS, 20),  # 100 Ronin XP
        study(d(0), ActivityKind.DEV_STUDY, 150),  # 300 Architect XP
    ]
    state = replay(events, CAL, today=d(0))
    assert state.jobs[Track.RONIN].level == 2
    assert state.jobs[Track.ARCHITECT].level == 3
    assert state.character_level == 5


def test_buying_a_stat_spends_held_souls_but_not_xp() -> None:
    events: list[Event] = [
        study(d(0), ActivityKind.DEV_STUDY, 150),
        bought(d(0), Stat.INTELLIGENCE, 200),
    ]
    state = replay(events, CAL, today=d(0))
    assert state.souls == 100
    assert state.souls_spent == 200
    assert state.stats[Stat.INTELLIGENCE] == 2
    assert (state.soul_level, state.level_cost) == (1, 240)
    assert state.jobs[Track.ARCHITECT].xp == 300


def test_recorded_prices_are_kept_but_never_overdraw() -> None:
    """Retuning activity souls later can leave less than a past purchase cost."""
    events: list[Event] = [reviews(d(0)), bought(d(0), Stat.VIGOR, 500)]
    state = replay(events, CAL, today=d(0))
    assert (state.souls, state.souls_spent, state.max_hp) == (0, 20, 110)


def test_spent_souls_are_not_in_the_bloodstain() -> None:
    events: list[Event] = [study(d(0), ActivityKind.DEV_STUDY, 150), bought(d(0), Stat.VIGOR, 200)]
    state = replay(events, CAL, today=d(2), effigies_per_week=0)
    assert state.bloodstain is not None and state.bloodstain.souls == 100


# --- Effigies -----------------------------------------------------------------


def test_an_effigy_takes_the_death_but_the_streak_breaks() -> None:
    # 2026-10-01 is a Thursday: d(1) and d(2) are spared, d(3) is a death.
    state = replay([reviews(d(0))], CAL, today=d(2))
    assert (state.deaths, state.hollowing, state.bloodstain) == (0, 0, None)
    assert (state.souls, state.effigies, state.effigies_used, state.streak) == (20, 1, 1, 0)
    assert [day.spared for day in state.recent_days] == [False, True, False]

    state = replay([reviews(d(0))], CAL, today=d(4))
    assert (state.deaths, state.effigies) == (1, 2)  # d(4) is Monday: refilled
    assert state.bloodstain is not None and state.bloodstain.souls == 20


def test_effigies_refill_on_monday_and_do_not_stack() -> None:
    # Thu lit, Fri and Sat spared, Sun dies, Mon refills and is spared, Tue lit, Wed spared.
    events: list[Event] = [reviews(d(0)), reviews(d(5))]
    state = replay(events, CAL, today=d(7))
    assert (state.deaths, state.effigies, state.effigies_used) == (1, 0, 4)

    quiet_week = replay([reviews(d(4)), *(reviews(d(n)) for n in range(5, 11))], CAL, today=d(11))
    assert quiet_week.effigies == 2


# --- service and page ---------------------------------------------------------


def earn(service: BonfireService, souls: int) -> None:
    service.log_study(ActivityKind.DEV_STUDY, souls // 2)


def test_levelling_up_needs_enough_souls(store: SqlEventStore, clock: FakeClock) -> None:
    service = BonfireService(store, clock, CAL)
    earn(service, 210)
    service.level_up(Stat.FAITH)
    with pytest.raises(CannotLevelUp, match="230 more souls"):
        service.level_up(Stat.FAITH)
    state = service.state()
    assert (state.stats[Stat.FAITH], state.souls) == (2, 10)


def test_stats_stop_at_the_maximum(store: SqlEventStore, clock: FakeClock) -> None:
    service = BonfireService(store, clock, CAL)
    for _ in range(STAT_MAX - 1):
        store.append(StatLevelled(clock.now(), Stat.VIGOR, 0))
    earn(service, 5_000)
    with pytest.raises(CannotLevelUp, match="already at 99"):
        service.level_up(Stat.VIGOR)


def test_level_up_from_the_page(client: TestClient) -> None:
    client.post("/log", data={"kind": "dev_study", "quantity": "120"})
    text = client.post("/level", data={"stat": "vigor"}, headers=HX).text
    assert "Vigor rose to 2. 200 souls spent at the bonfire." in text
    assert "110 HP in boss fights" in text
    assert 'Next level costs <strong class="souls-ink">240</strong>' in text

    text = client.post("/level", data={"stat": "faith"}, headers=HX).text
    assert "You need 200 more souls." in text
    assert "disabled" in text


def test_character_panel_shows_jobs_and_effigies(client: TestClient) -> None:
    client.post("/log", data={"kind": "dev_study", "quantity": "75"})
    page = client.get("/").text
    assert "Character · level 3" in page
    assert "50 / 200 XP to level 3" in page
    assert "2 of 2 Effigies left this week" in page
    assert client.post("/level", data={"stat": "luck"}).status_code == 422


def test_purchases_reject_bad_input() -> None:
    from datetime import datetime

    with pytest.raises(ValueError, match="negative"):
        StatLevelled(at(d(0)), Stat.VIGOR, -1)
    with pytest.raises(ValueError, match="timezone"):
        StatLevelled(datetime(2026, 10, 1, 12), Stat.VIGOR, 200)
