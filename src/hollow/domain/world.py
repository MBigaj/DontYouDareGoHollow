"""Replays the event log day by day into the current state of the world.

Rules (from the plan):
- A day is lit when any activity reaches its kindling amount (e.g. 10 Anki reviews).
- Missing a day is a death: your held souls drop as a bloodstain. Any older bloodstain is lost.
- Lighting the bonfire on a later day recovers the bloodstain. Miss again first and it is gone.
- Each missed day adds one step of hollowing (max 5); each lit day removes one.
- Today is never a death: it is still in progress.
- An Effigy spares a missed day: no death, no bloodstain, no hollowing, but the streak breaks.
  You get 2 a week; they refill when the game week starts (Monday 04:00) and do not stack.
- Souls spent on stats leave your held souls. Job XP is souls earned per track, never lost.
"""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta

from hollow.domain.activities import ACTIVITIES, ActivityKind, Track, lights_bonfire, souls_for
from hollow.domain.armory import SIPHON_PERCENT, WEAPONS, Armory, Skill
from hollow.domain.armory import build as build_armory
from hollow.domain.bosses import BossRecord
from hollow.domain.bosses import track as track_bosses
from hollow.domain.calendar import GameCalendar
from hollow.domain.events import (
    Event,
    MessageLeft,
    StatLevelled,
    StudyLogged,
    WeaponBought,
    WeaponUpgraded,
)
from hollow.domain.lessons import LessonOutcome, LessonProgress, track
from hollow.domain.lessons import Run as LessonRun
from hollow.domain.progression import (
    STAT_START,
    JobProgress,
    Stat,
    job_progress,
    level_cost,
    max_hp,
    mistake_cost,
)

MAX_HOLLOWING = 5
EFFIGIES_PER_WEEK = 2


@dataclass(frozen=True)
class Bloodstain:
    souls: int
    dropped_on: date


@dataclass(frozen=True)
class DaySummary:
    day: date
    souls_earned: int
    lit: bool
    died: bool
    spared: bool = False
    """Missed, but an Effigy took the death."""


@dataclass(frozen=True)
class Message:
    text: str
    left_on: date


@dataclass(frozen=True)
class WorldState:
    today: date
    souls: int
    bloodstain: Bloodstain | None
    hollowing: int
    lit_today: bool
    streak: int
    bonfires_lit: int
    deaths: int
    souls_lost: int
    souls_earned_total: int
    today_totals: dict[ActivityKind, int]
    recent_days: tuple[DaySummary, ...]
    message: Message | None
    """The newest message left before today, shown at the bonfire as 'left by past you'."""
    stats: dict[Stat, int]
    souls_spent: int
    effigies: int
    """Effigies left this week."""
    effigies_used: int
    jobs: dict[Track, JobProgress]
    today_souls: dict[ActivityKind, int]
    lessons: dict[str, LessonProgress]
    today_lessons: tuple[LessonOutcome, ...]
    bosses: dict[str, BossRecord]
    today_boss_souls: int
    armory: Armory

    @property
    def lessons_due(self) -> int:
        return sum(1 for p in self.lessons.values() if p.is_due(self.today))

    @property
    def soul_level(self) -> int:
        """Stat levels bought so far."""
        return sum(level - STAT_START for level in self.stats.values())

    @property
    def character_level(self) -> int:
        return sum(job.level for job in self.jobs.values())

    @property
    def level_cost(self) -> int:
        return level_cost(self.soul_level)

    @property
    def can_level_up(self) -> bool:
        return self.souls >= self.level_cost

    @property
    def max_hp(self) -> int:
        return max_hp(self.stats[Stat.VIGOR])

    @property
    def mistake_cost(self) -> int:
        return mistake_cost(self.stats[Stat.ENDURANCE])

    @property
    def status(self) -> str:
        if self.hollowing == 0:
            return "Human"
        if self.hollowing < 3:
            return "Fading"
        if self.hollowing < MAX_HOLLOWING:
            return "Hollowing"
        return "Hollow"


def replay(
    events: Iterable[Event],
    calendar: GameCalendar,
    today: date,
    recent: int = 7,
    effigies_per_week: int = EFFIGIES_PER_WEEK,
) -> WorldState:
    events = list(events)
    totals_by_day: dict[date, dict[ActivityKind, int]] = defaultdict(lambda: defaultdict(int))
    souls_by_day: dict[date, int] = defaultdict(int)
    today_souls: dict[ActivityKind, int] = defaultdict(int)
    lessons_cleared_by_day: dict[date, int] = defaultdict(int)
    purchases_by_day: dict[date, list[StatLevelled | WeaponBought | WeaponUpgraded]] = defaultdict(
        list
    )
    xp: dict[Track, int] = dict.fromkeys(Track, 0)
    message: Message | None = None
    message_key: tuple[date, float] | None = None

    for event in events:
        day = calendar.day_of(event.occurred_at)
        if day > today:
            continue
        if isinstance(event, StudyLogged):
            totals_by_day[day][event.kind] += event.quantity
            souls_by_day[day] += souls_for(event.kind, event.quantity)
            xp[ACTIVITIES[event.kind].track] += souls_for(event.kind, event.quantity)
            if day == today:
                today_souls[event.kind] += souls_for(event.kind, event.quantity)
        elif isinstance(event, StatLevelled | WeaponBought | WeaponUpgraded):
            purchases_by_day[day].append(event)
        elif isinstance(event, MessageLeft) and day < today:
            key = (day, event.occurred_at.timestamp())
            if message_key is None or key > message_key:
                message, message_key = Message(event.text.strip(), day), key

    bosses = track_bosses(events, calendar, today)
    today_boss_souls = 0
    for record in bosses.values():
        for reward in record.rewards:
            souls_by_day[reward.day] += reward.souls
            xp[Track.RONIN] += reward.souls
            if reward.lights:
                lessons_cleared_by_day[reward.day] += 1
            if reward.day == today:
                today_boss_souls += reward.souls

    defeated = {b: r.defeated_at for b, r in bosses.items() if r.defeated_at is not None}
    armory = build_armory([e for e in events if calendar.day_of(e.occurred_at) <= today], defeated)

    outcomes, lessons = track(events, calendar, today)
    for outcome in outcomes:
        souls = outcome.souls
        if WEAPONS[armory.equipped_at(Track.RONIN, outcome.at)].skill is Skill.SOUL_SIPHON:
            souls += (souls * SIPHON_PERCENT + 50) // 100
        souls_by_day[outcome.day] += souls
        xp[Track.RONIN] += souls
        if outcome.passed and outcome.run is not LessonRun.PRACTICE:
            lessons_cleared_by_day[outcome.day] += 1

    souls = 0
    bloodstain: Bloodstain | None = None
    hollowing = 0
    bonfires_lit = deaths = souls_lost = souls_earned_total = souls_spent = 0
    stats = dict.fromkeys(Stat, STAT_START)
    effigies = effigies_per_week
    effigies_used = 0
    history: list[DaySummary] = []

    first_day = min([*totals_by_day, *purchases_by_day, *souls_by_day], default=today)
    day = first_day
    while day <= today:
        if day.weekday() == 0:
            effigies = effigies_per_week
        earned = souls_by_day.get(day, 0)
        lit = lights_bonfire(dict(totals_by_day.get(day, {}))) or lessons_cleared_by_day[day] > 0
        souls += earned
        souls_earned_total += earned
        for purchase in purchases_by_day.get(day, []):
            if isinstance(purchase, StatLevelled):
                stats[purchase.stat] += 1
            spent = min(souls, purchase.cost)
            souls -= spent
            souls_spent += spent
        died = spared = False

        if lit:
            bonfires_lit += 1
            hollowing = max(0, hollowing - 1)
            if bloodstain is not None:
                souls += bloodstain.souls
                bloodstain = None
        elif day < today and effigies > 0:
            spared = True
            effigies -= 1
            effigies_used += 1
        elif day < today:
            died = True
            deaths += 1
            hollowing = min(MAX_HOLLOWING, hollowing + 1)
            if bloodstain is not None:
                souls_lost += bloodstain.souls
            bloodstain = Bloodstain(souls, day) if souls > 0 else None
            souls = 0

        history.append(DaySummary(day, earned, lit, died, spared))
        day += timedelta(days=1)

    return WorldState(
        today=today,
        souls=souls,
        bloodstain=bloodstain,
        hollowing=hollowing,
        lit_today=history[-1].lit,
        streak=_streak(history),
        bonfires_lit=bonfires_lit,
        deaths=deaths,
        souls_lost=souls_lost,
        souls_earned_total=souls_earned_total,
        today_totals=dict(totals_by_day.get(today, {})),
        recent_days=tuple(reversed(history[-recent:])),
        message=message,
        stats=stats,
        souls_spent=souls_spent,
        effigies=effigies,
        effigies_used=effigies_used,
        jobs={t: job_progress(t, xp[t]) for t in Track},
        today_souls=dict(today_souls),
        lessons=lessons,
        today_lessons=tuple(o for o in outcomes if o.day == today),
        bosses=bosses,
        today_boss_souls=today_boss_souls,
        armory=armory,
    )


def _streak(history: list[DaySummary]) -> int:
    """Consecutive lit days ending today, or ending yesterday while today is still open."""
    days = list(reversed(history))
    if days and not days[0].lit:
        days = days[1:]
    count = 0
    for summary in days:
        if not summary.lit:
            break
        count += 1
    return count
