"""Replays the event log day by day into the current state of the world.

Rules (from the plan):
- A day is lit when any activity reaches its kindling amount (e.g. 10 Anki reviews).
- Missing a day is a death: your held souls drop as a bloodstain. Any older bloodstain is lost.
- Lighting the bonfire on a later day recovers the bloodstain. Miss again first and it is gone.
- Each missed day adds one step of hollowing (max 5); each lit day removes one.
- Today is never a death: it is still in progress.
"""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta

from hollow.domain.activities import ActivityKind, lights_bonfire, souls_for
from hollow.domain.calendar import GameCalendar
from hollow.domain.events import Event, MessageLeft, StudyLogged

MAX_HOLLOWING = 5


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
    events: Iterable[Event], calendar: GameCalendar, today: date, recent: int = 7
) -> WorldState:
    totals_by_day: dict[date, dict[ActivityKind, int]] = defaultdict(lambda: defaultdict(int))
    souls_by_day: dict[date, int] = defaultdict(int)
    message: Message | None = None
    message_key: tuple[date, float] | None = None

    for event in events:
        day = calendar.day_of(event.occurred_at)
        if day > today:
            continue
        if isinstance(event, StudyLogged):
            totals_by_day[day][event.kind] += event.quantity
            souls_by_day[day] += souls_for(event.kind, event.quantity)
        elif isinstance(event, MessageLeft) and day < today:
            key = (day, event.occurred_at.timestamp())
            if message_key is None or key > message_key:
                message, message_key = Message(event.text.strip(), day), key

    souls = 0
    bloodstain: Bloodstain | None = None
    hollowing = 0
    bonfires_lit = deaths = souls_lost = souls_earned_total = 0
    history: list[DaySummary] = []

    first_day = min(totals_by_day, default=today)
    day = first_day
    while day <= today:
        earned = souls_by_day.get(day, 0)
        lit = lights_bonfire(dict(totals_by_day.get(day, {})))
        souls += earned
        souls_earned_total += earned
        died = False

        if lit:
            bonfires_lit += 1
            hollowing = max(0, hollowing - 1)
            if bloodstain is not None:
                souls += bloodstain.souls
                bloodstain = None
        elif day < today:
            died = True
            deaths += 1
            hollowing = min(MAX_HOLLOWING, hollowing + 1)
            if bloodstain is not None:
                souls_lost += bloodstain.souls
            bloodstain = Bloodstain(souls, day) if souls > 0 else None
            souls = 0

        history.append(DaySummary(day, earned, lit, died))
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
