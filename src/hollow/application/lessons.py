"""Running lessons: picking questions, checking answers, recording finished runs.

The server keeps no lesson state between requests. A run carries its id, its questions
(as the verbs' written forms) and the answers so far; finishing re-grades everything here,
and the run id makes a resubmitted finish a no-op.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from random import SystemRandom
from uuid import UUID, uuid4, uuid5

from hollow.application.ports import Clock, EventStore
from hollow.domain.calendar import GameCalendar
from hollow.domain.conjugation import Verb
from hollow.domain.events import LessonCompleted
from hollow.domain.lessons import LESSONS, LessonOutcome, LessonProgress, LessonSpec, grade
from hollow.domain.vocabulary import known_verbs
from hollow.domain.world import WorldState, replay

RUNS_NAMESPACE = UUID("8c0e5a7d-3f61-4b2c-9e48-1d6a2f9b7c35")


class LessonError(ValueError):
    """An unknown lesson, one without enough verbs yet, or a tampered run."""


class Status(StrEnum):
    LOCKED = "locked"
    NEW = "new"
    DUE = "due"
    WAITING = "waiting"


@dataclass(frozen=True)
class LessonCard:
    spec: LessonSpec
    verbs: int
    questions: int
    status: Status
    progress: LessonProgress | None


@dataclass(frozen=True)
class Run:
    id: UUID
    spec: LessonSpec
    questions: list[Verb]


class LessonService:
    def __init__(self, store: EventStore, clock: Clock, calendar: GameCalendar) -> None:
        self._store = store
        self._clock = clock
        self._calendar = calendar

    def state(self) -> WorldState:
        today = self._calendar.day_of(self._clock.now())
        return replay(self._store.all(), self._calendar, today)

    def verbs(self) -> list[Verb]:
        return known_verbs(self._store.all())

    def overview(self) -> list[LessonCard]:
        verbs = self.verbs()
        state = self.state()
        cards = []
        for spec in LESSONS.values():
            progress = state.lessons.get(spec.id)
            if not spec.available(verbs):
                status = Status.LOCKED
            elif progress is None or not progress.cleared:
                status = Status.NEW
            elif progress.is_due(state.today):
                status = Status.DUE
            else:
                status = Status.WAITING
            cards.append(
                LessonCard(
                    spec,
                    len(spec.pool(verbs)),
                    spec.question_count(verbs),
                    status,
                    progress,
                )
            )
        return cards

    def spec(self, lesson_id: str) -> LessonSpec:
        try:
            return LESSONS[lesson_id]
        except KeyError:
            raise LessonError(f"There is no lesson called {lesson_id}.") from None

    def start(self, lesson_id: str) -> Run:
        spec = self.spec(lesson_id)
        verbs = self.verbs()
        if not spec.available(verbs):
            raise LessonError(f"{spec.title} needs {spec.min_verbs} learned verbs first.")
        seed = SystemRandom().randrange(2**32)
        return Run(uuid4(), spec, spec.questions(verbs, seed))

    def resume(self, lesson_id: str, run_id: str, written: Sequence[str]) -> Run:
        """Rebuilds a run from what the page sent back, checking it against your verbs."""
        spec = self.spec(lesson_id)
        pool = {v.written: v for v in spec.pool(self.verbs())}
        try:
            questions = [pool[w] for w in written]
            run = UUID(run_id)
        except (KeyError, ValueError):
            raise LessonError(
                "This lesson run does not match your verbs. Start it again."
            ) from None
        if not 0 < len(questions) <= spec.size:
            raise LessonError("This lesson run has the wrong number of questions.")
        return Run(run, spec, questions)

    def finish(self, run: Run, answers: Sequence[str]) -> tuple[LessonOutcome, WorldState]:
        if len(answers) != len(run.questions):
            raise LessonError("Answer every question before finishing.")
        correct = sum(grade(run.questions, answers))
        event = LessonCompleted(
            self._clock.now(),
            run.spec.id,
            correct,
            len(run.questions),
            id=uuid5(RUNS_NAMESPACE, str(run.id)),
        )
        self._store.append_new([event])
        state = self.state()
        outcome = next(o for o in state.lessons[run.spec.id].history if o.event_id == event.id)
        return outcome, state
