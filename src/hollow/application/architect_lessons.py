"""Architect lessons: read a step, then answer its quiz. Graded and recorded like a Japanese
lesson (an `arch:<step>` run), so clears, refreshers, souls and titanite work the same.

The server keeps no state between requests: a run carries its id and its question ids, and
the shown order of each question's options is derived from the run id.
"""

import random
from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID, uuid4

from hollow.application.lessons import LessonError, LessonService
from hollow.application.ports import Clock, EventStore
from hollow.domain.architect import QUESTIONS, REGION_BY_ID, TOPICS, lesson_id
from hollow.domain.calendar import GameCalendar
from hollow.domain.curriculum import QuizQuestion, Topic
from hollow.domain.events import Material
from hollow.domain.lessons import LessonOutcome
from hollow.domain.world import WorldState


@dataclass(frozen=True)
class QuizRun:
    id: UUID
    topic: Topic
    questions: list[QuizQuestion]

    def order(self, n: int) -> list[int]:
        """The written options of question `n`, in the order this run shows them."""
        order = list(range(len(self.questions[n].options)))
        random.Random(f"{self.id}:{self.questions[n].id}").shuffle(order)
        return order

    def options(self, n: int) -> list[str]:
        return [self.questions[n].options[i] for i in self.order(n)]

    def accepts(self, n: int, answer: str) -> bool:
        """`answer` is the shown position of the chosen option, from 0."""
        try:
            shown = int(answer)
        except ValueError:
            return False
        order = self.order(n)
        return 0 <= shown < len(order) and order[shown] == self.questions[n].answer

    def grade(self, answers: Sequence[str]) -> list[bool]:
        return [self.accepts(n, a) for n, a in enumerate(answers)]


class ArchitectLessons:
    def __init__(self, store: EventStore, clock: Clock, calendar: GameCalendar) -> None:
        self._lessons = LessonService(store, clock, calendar)

    def state(self) -> WorldState:
        return self._lessons.state()

    def topic(self, topic_id: str) -> Topic:
        """A step you can play: written, in a region that is open."""
        topic = TOPICS.get(topic_id)
        if topic is None:
            raise LessonError(f"There is no Architect step called {topic_id}.")
        if not topic.playable:
            raise LessonError(f"{topic.title} has no lesson yet.")
        if not self.state().architect.region_open(topic.region):
            raise LessonError(f"{REGION_BY_ID[topic.region].name} is still in the fog.")
        return topic

    def start(self, topic_id: str) -> QuizRun:
        topic = self.topic(topic_id)
        questions = list(topic.quiz)
        random.shuffle(questions)
        return QuizRun(uuid4(), topic, questions)

    def resume(self, topic_id: str, run_id: str, asked: Sequence[str]) -> QuizRun:
        """Rebuilds a run from what the page sent back, checking it against the step."""
        topic = self.topic(topic_id)
        own = {q.id for q in topic.quiz}
        try:
            run = UUID(run_id)
        except ValueError:
            raise LessonError("This quiz run is broken. Start it again.") from None
        if not asked or len(set(asked)) != len(asked) or not set(asked) <= own:
            raise LessonError("This quiz run does not match the step. Start it again.")
        return QuizRun(run, topic, [QUESTIONS[q] for q in asked])

    def finish(
        self, run: QuizRun, answers: Sequence[str], roll: float | None = None
    ) -> tuple[LessonOutcome, Material | None, WorldState]:
        if len(answers) != len(run.questions):
            raise LessonError("Answer every question before finishing.")
        marks = run.grade(answers)
        missed = tuple(q.id for q, ok in zip(run.questions, marks, strict=True) if not ok)
        return self._lessons.record(
            lesson_id(run.topic.id), run.id, sum(marks), len(run.questions), missed, roll
        )
