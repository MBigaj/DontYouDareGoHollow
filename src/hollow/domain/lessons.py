"""Lessons: short typed drills built from the words you have learned.

Rewards and timing (from the plan):
- A lesson is cleared at 80% or better. Any finished run pays souls for its score.
- First clear pays 100% of the lesson's souls. A cleared lesson comes back as a refresher
  1, 3, 7, 21, then 60 days later. A due refresher pays 60%; practising before it is due
  pays 25% and does not move the schedule.
- A due refresher at 90% or better moves to the next interval; 80-89% repeats the same
  interval; a failed refresher stays due.
- Clearing a lesson (or a due refresher) lights the bonfire, like a grammar drill.
"""

import random
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import StrEnum
from uuid import UUID

from hollow.domain.calendar import GameCalendar
from hollow.domain.conjugation import Ending, Verb
from hollow.domain.events import Event, LessonCompleted

CLEAR = 0.8
ADVANCE = 0.9
SOULS_PER_QUESTION = 5
INTERVALS = (1, 3, 7, 21, 60)


class Run(StrEnum):
    FIRST = "first"
    """Not cleared before: full souls."""
    REFRESHER = "refresher"
    """Cleared before and due again."""
    PRACTICE = "practice"
    """Cleared before but not due yet."""


MULTIPLIER = {Run.FIRST: 1.0, Run.REFRESHER: 0.6, Run.PRACTICE: 0.25}


@dataclass(frozen=True)
class LessonSpec:
    id: str
    title: str
    example: str
    endings: frozenset[Ending]
    size: int = 10
    min_verbs: int = 2

    def pool(self, verbs: Iterable[Verb]) -> list[Verb]:
        return [v for v in verbs if v.ending in self.endings]

    def available(self, verbs: Iterable[Verb]) -> bool:
        return len(self.pool(verbs)) >= self.min_verbs

    def question_count(self, verbs: Iterable[Verb]) -> int:
        return min(self.size, max(len(self.pool(verbs)), 5))

    def questions(self, verbs: Iterable[Verb], seed: int) -> list[Verb]:
        """Shuffled rounds through the pool, never the same verb twice in a row."""
        pool = self.pool(verbs)
        rng = random.Random(seed)
        out: list[Verb] = []
        while len(out) < self.question_count(pool):
            batch = pool[:]
            rng.shuffle(batch)
            if out and len(batch) > 1 and batch[0] == out[-1]:
                batch.append(batch.pop(0))
            out.extend(batch)
        return out[: self.question_count(pool)]


ALL = frozenset(Ending)
LESSONS: dict[str, LessonSpec] = {
    s.id: s
    for s in (
        LessonSpec("te-ru", "る-verbs", "食べる → 食べて", frozenset({Ending.RU_VERB})),
        LessonSpec("te-tsu", "う・つ・る → って", "買う → 買って", frozenset({Ending.TSU})),
        LessonSpec("te-nde", "む・ぶ・ぬ → んで", "飲む → 飲んで", frozenset({Ending.NDE})),
        LessonSpec(
            "te-ite",
            "く・ぐ → いて・いで",
            "書く → 書いて, 行く → 行って",
            frozenset({Ending.ITE}),
        ),
        LessonSpec("te-shite", "す → して", "話す → 話して", frozenset({Ending.SHITE})),
        LessonSpec(
            "te-irregular",
            "する and 来る",
            "する → して, 来る → 来て",
            frozenset({Ending.IRREGULAR}),
        ),
        LessonSpec("te-mixed", "Mixed て-form", "Every group, shuffled", ALL, size=12, min_verbs=6),
    )
}


@dataclass(frozen=True)
class LessonOutcome:
    event_id: UUID
    lesson_id: str
    day: date
    run: Run
    correct: int
    total: int
    souls: int

    @property
    def passed(self) -> bool:
        return self.correct >= CLEAR * self.total


@dataclass
class LessonProgress:
    lesson_id: str
    attempts: int = 0
    best: float = 0.0
    step: int = -1
    """Index into INTERVALS; -1 until first cleared."""
    due_on: date | None = None
    history: list[LessonOutcome] = field(default_factory=list)

    @property
    def cleared(self) -> bool:
        return self.step >= 0

    def run_on(self, day: date) -> Run:
        if not self.cleared:
            return Run.FIRST
        assert self.due_on is not None
        return Run.REFRESHER if day >= self.due_on else Run.PRACTICE

    def is_due(self, day: date) -> bool:
        return self.cleared and self.due_on is not None and day >= self.due_on


def souls_for_run(run: Run, correct: int) -> int:
    return round(SOULS_PER_QUESTION * correct * MULTIPLIER[run])


def track(
    events: Iterable[Event], calendar: GameCalendar, today: date
) -> tuple[list[LessonOutcome], dict[str, LessonProgress]]:
    """Replays lesson runs in order into rewards and each lesson's refresher schedule."""
    progress: dict[str, LessonProgress] = {}
    outcomes: list[LessonOutcome] = []
    runs = sorted(
        (e for e in events if isinstance(e, LessonCompleted)), key=lambda e: e.occurred_at
    )
    for event in runs:
        day = calendar.day_of(event.occurred_at)
        if day > today:
            continue
        p = progress.setdefault(event.lesson_id, LessonProgress(event.lesson_id))
        run = p.run_on(day)
        outcome = LessonOutcome(
            event.id,
            event.lesson_id,
            day,
            run,
            event.correct,
            event.total,
            souls_for_run(run, event.correct),
        )
        p.attempts += 1
        p.best = max(p.best, event.score)
        p.history.append(outcome)
        outcomes.append(outcome)
        if not outcome.passed:
            continue
        if run is Run.FIRST:
            p.step = 0
        elif run is Run.REFRESHER and event.score >= ADVANCE:
            p.step = min(p.step + 1, len(INTERVALS) - 1)
        if run is not Run.PRACTICE:
            p.due_on = day + timedelta(days=INTERVALS[p.step])
    return outcomes, progress


def grade(questions: Sequence[Verb], answers: Sequence[str]) -> list[bool]:
    return [q.te_form.accepts(a) for q, a in zip(questions, answers, strict=True)]
