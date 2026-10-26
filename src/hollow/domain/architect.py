"""The Architect road: eight skill regions of senior backend steps, and the nine Lords of
Design that wait behind them.

The steps live in the repo as Markdown (hollow/curriculum/architect), one file per step. The
curriculum is personal: it starts from three years of backend work (Python, FastAPI,
PostgreSQL, MongoDB, RabbitMQ, Kubernetes, Docker, AWS) and keeps only what is left to earn,
weighted towards distributed systems and architecture.

Played like the Japanese road (from the plan):
- A step is a lesson: read it, then pass its quiz at 80% (`arch:<step>` lesson runs). That
  clears it, lights the bonfire and starts its refreshers.
- Prove (optional): a Tech Lead exam at 80% or better pays extra and marks the step proved.
  A region's placement trial clears the steps you already know.
- When every step of a region is cleared, its boss waits behind the fog. Felling it opens the
  next region, once that region's lessons are written and its map is charted.
- A Lord of Design opens when the bosses of all the regions it needs have fallen.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any

from hollow.curriculum import load
from hollow.domain.atlas import ARCH_REGION_MAPS
from hollow.domain.calendar import GameCalendar
from hollow.domain.curriculum import QuizQuestion, SkillRegion, Topic
from hollow.domain.events import AgentResult, Event
from hollow.domain.lessons import LessonProgress

PROVE_MARK = 0.8
PROVE_SOULS = 120
LESSON_PREFIX = "arch:"
"""Architect lesson runs are recorded as `arch:<step id>`."""

REGIONS: tuple[SkillRegion, ...] = load()
REGION_BY_ID = {r.id: r for r in REGIONS}
TOPICS: dict[str, Topic] = {t.id: t for r in REGIONS for t in r.topics}
QUESTIONS: dict[str, QuizQuestion] = {q.id: q for t in TOPICS.values() for q in t.quiz}
ALL_REGIONS = tuple(r.id for r in REGIONS)


def lesson_id(topic_id: str) -> str:
    return LESSON_PREFIX + topic_id


def topic_of(lesson: str) -> Topic | None:
    """The step behind an `arch:` lesson id, if it is one."""
    if not lesson.startswith(LESSON_PREFIX):
        return None
    return TOPICS.get(lesson.removeprefix(LESSON_PREFIX))


def region_topics(region_id: str) -> list[Topic]:
    return [t for t in TOPICS.values() if t.region == region_id]


def boss_id(region_id: str) -> str:
    return f"{region_id}-boss"


@dataclass(frozen=True)
class Lord:
    id: str
    name: str
    tier: int
    regions: tuple[str, ...]
    forces: str


LORDS: tuple[Lord, ...] = (
    Lord("url-shortener", "URL Shortener", 1, ("data-depths", "api-citadel"),
         "Estimation, key generation, read-heavy caching"),
    Lord("rate-limiter", "Rate Limiter", 1, ("data-depths",),
         "Algorithms, distributed counters, accepting inaccuracy"),
    Lord("file-upload", "File Upload", 1, ("api-citadel",),
         "Object storage, presigned URLs, async processing"),
    Lord("notification-system", "Notification System", 2, ("async-ruins",),
         "Fan-out, retries, DLQs, delivery guarantees"),
    Lord("payment-system", "Payment System", 2, ("async-ruins", "data-depths"),
         "Idempotency, transactions, sagas, reconciliation"),
    Lord("search-system", "Search System", 2, ("data-depths",),
         "Indexing pipelines, Elasticsearch, consistency lag"),
    Lord("social-feed", "Social Feed", 3, ("distributed-abyss",),
         "Fan-out on write vs read, caching at scale"),
    Lord("large-e-commerce", "Large E-commerce", 3, ALL_REGIONS,
         "Service boundaries, inventory consistency, peak traffic"),
    Lord("uber-or-netflix-like-platform", "Uber- or Netflix-like Platform", 3, ALL_REGIONS,
         "Geo data or streaming, multi-region, cost"),
)  # fmt: skip


# --- progress -----------------------------------------------------------------


@dataclass
class TopicState:
    topic: Topic
    lesson: LessonProgress | None = None
    proved: bool = False
    placed: bool = False
    """Cleared by a placement trial rather than a lesson or an exam."""
    best: float | None = None
    """Best exam score, 0 to 1."""
    exams: int = 0

    @property
    def cleared(self) -> bool:
        return self.proved or (self.lesson is not None and self.lesson.cleared)


@dataclass(frozen=True)
class ArchitectReward:
    day: date
    souls: int
    lights: bool


@dataclass
class ArchitectState:
    topics: dict[str, TopicState]
    placed_regions: set[str]
    rewards: list[ArchitectReward]
    felled: set[str]
    """Regions whose boss has fallen."""

    def region(self, region_id: str) -> list[TopicState]:
        return [s for s in self.topics.values() if s.topic.region == region_id]

    def region_ready(self, region_id: str) -> bool:
        """Every step cleared: the boss's fog parts."""
        return all(s.cleared for s in self.region(region_id))

    def region_open(self, region_id: str) -> bool:
        region = REGION_BY_ID[region_id]
        if not region.written or region_id not in ARCH_REGION_MAPS:
            return False  # nothing to play yet, or no map to walk it on
        return region.number == 1 or REGIONS[region.number - 2].id in self.felled

    def lord_open(self, lord: Lord) -> bool:
        return all(r in self.felled for r in lord.regions)


def exam_score(payload: Mapping[str, Any]) -> float:
    if payload.get("total") is not None:
        return float(payload["total"])
    scored = [q for q in payload.get("questions", []) if isinstance(q, Mapping)]
    if not scored:
        return 0.0
    return sum(int(q["score"]) for q in scored) / (3 * len(scored))


def track(
    events: Iterable[Event],
    calendar: GameCalendar,
    today: date,
    lessons: Mapping[str, LessonProgress],
    felled: Iterable[str],
) -> ArchitectState:
    """Exams, placements and lesson progress per step. `felled` names the bosses down."""
    down = set(felled)
    state = ArchitectState(
        {t: TopicState(topic, lessons.get(lesson_id(t))) for t, topic in TOPICS.items()},
        set(),
        [],
        {r.id for r in REGIONS if boss_id(r.id) in down},
    )
    for event in sorted(events, key=lambda e: e.occurred_at):
        if not isinstance(event, AgentResult) or event.agent != "tech-lead":
            continue
        day = calendar.day_of(event.occurred_at)
        if day > today:
            continue
        kind, _, key = event.task.partition(":")
        if kind == "exam" and key in state.topics:
            topic = state.topics[key]
            score = exam_score(event.payload)
            topic.exams += 1
            topic.best = max(topic.best or 0.0, score)
            if score >= PROVE_MARK and not topic.proved:
                topic.proved = True
                state.rewards.append(ArchitectReward(day, PROVE_SOULS, lights=True))
        elif kind == "placement" and key in REGION_BY_ID:
            state.placed_regions.add(key)
            for topic_id in event.payload.get("cleared", []):
                placed = state.topics.get(str(topic_id))
                if placed is not None and placed.topic.region == key and not placed.proved:
                    placed.proved = placed.placed = True
    return state
