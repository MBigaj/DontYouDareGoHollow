"""Daily quests from the Quest Master, checked by code.

The Quest Master (an agent) only proposes quests. Whether one is done, and what it pays,
is decided here from the event log: an agent's suggested bonus is capped at 100 souls per
quest and 250 per day, and a "judged" quest needs a Sensei verdict.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from hollow.domain.activities import ActivityKind
from hollow.domain.bosses import Attempt
from hollow.domain.events import AgentResult, Event
from hollow.domain.lessons import LessonOutcome

MAX_BONUS = 100
DAY_CAP = 250


@dataclass(frozen=True)
class Quest:
    id: str
    title: str
    why: str
    check: Mapping[str, Any]
    bonus: int
    roulette: bool = False

    @property
    def judged(self) -> bool:
        return self.check.get("kind") == "judged"


@dataclass(frozen=True)
class QuestStatus:
    quest: Quest
    done: bool
    bonus: int
    """Souls actually paid, after the caps; 0 until done."""


def issued(events: Iterable[Event]) -> dict[date, list[Quest]]:
    """The quests issued for each day: the first Quest Master result for that day wins."""
    by_day: dict[date, list[Quest]] = {}
    for event in sorted(events, key=lambda e: e.occurred_at):
        if not isinstance(event, AgentResult) or event.agent != "quest-master":
            continue
        day = date.fromisoformat(str(event.payload["day"]))
        if day in by_day:
            continue
        quests = [quest(q) for q in event.payload.get("quests", [])]
        if event.payload.get("roulette"):
            quests.append(quest(event.payload["roulette"], roulette=True))
        by_day[day] = quests
    return by_day


def quest(raw: Mapping[str, Any], roulette: bool = False) -> Quest:
    return Quest(
        id=str(raw["id"]),
        title=str(raw["title"]),
        why=str(raw.get("why", "")),
        check=dict(raw["check"]),
        bonus=int(raw.get("bonus_souls", 0)),
        roulette=roulette,
    )


def verdicts(events: Iterable[Event]) -> dict[str, bool]:
    """Sensei verdicts by task; the latest one for a task counts."""
    found: dict[str, bool] = {}
    for event in sorted(events, key=lambda e: e.occurred_at):
        if isinstance(event, AgentResult) and event.agent == "sensei":
            found[event.task] = bool(event.payload.get("passed"))
    return found


def done(
    q: Quest,
    totals: Mapping[ActivityKind, int],
    lessons: Sequence[LessonOutcome],
    attempts: Sequence[Attempt],
    judged: Mapping[str, bool],
) -> bool:
    check = q.check
    kind = check.get("kind")
    if kind == "lesson":
        need = float(check.get("min_score", 0.8))
        return any(
            o.lesson_id == check["lesson_id"] and o.correct >= need * o.total for o in lessons
        )
    if kind == "anki":
        return totals.get(ActivityKind.ANKI_REVIEWS, 0) >= int(
            check.get("reviews", 0)
        ) and totals.get(ActivityKind.ANKI_NEW_CARDS, 0) >= int(check.get("new_cards", 0))
    if kind == "study":
        return totals.get(ActivityKind(check["activity"]), 0) >= int(check["amount"])
    if kind == "boss":
        return any(
            a.boss_id == check["boss_id"] and a.phase + 1 >= int(check["phase"]) for a in attempts
        )
    if kind == "judged":
        return judged.get(f"quest:{q.id}", False)
    return False


def evaluate(
    quests: Sequence[Quest],
    totals: Mapping[ActivityKind, int],
    lessons: Sequence[LessonOutcome],
    attempts: Sequence[Attempt],
    judged: Mapping[str, bool],
) -> list[QuestStatus]:
    left = DAY_CAP
    out = []
    for q in quests:
        ok = done(q, totals, lessons, attempts, judged)
        pay = min(max(q.bonus, 0), MAX_BONUS, left) if ok else 0
        left -= pay
        out.append(QuestStatus(q, ok, pay))
    return out
