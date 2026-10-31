"""Lessons: short typed drills built from the words you have learned.

Rewards and timing (from the plan):
- A lesson is cleared at 80% or better. Any finished run pays souls for its score.
- First clear pays 100% of the lesson's souls. A cleared lesson comes back as a refresher
  1, 3, 7, 21, then 60 days later. A due refresher pays 60%; practising before it is due
  pays 25% and does not move the schedule.
- A due refresher at 90% or better moves to the next interval; 80-89% repeats the same
  interval; a failed refresher stays due.
- Clearing a lesson (or a due refresher) lights the bonfire, like a grammar drill.
- Each lesson drills one or more forms (て, 〜ている, 〜た, 〜ない, 〜なかった) and belongs to a
  Ronin region. A region past Firelink opens when the boss before it falls (REGION_GATES).
"""

import random
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import StrEnum
from uuid import UUID

from hollow.domain.calendar import GameCalendar
from hollow.domain.conjugation import FORM_NAMES, Ending, Form, TeForm, Verb
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
    example: tuple[tuple[str, str], ...]
    """Pairs of (written, kana): dictionary form → て-form, possibly twice."""
    endings: frozenset[Ending]
    size: int = 10
    min_verbs: int = 2
    forms: tuple[Form, ...] = (Form.TE,)
    """What each question asks for, in turn: question n asks forms[n % len(forms)]."""
    region: str = "firelink"
    """The Ronin region (atlas.REGIONS) the lesson belongs to."""
    skip: frozenset[str] = frozenset()
    """Verbs (as written) left out of this drill, e.g. ある in 〜ている."""

    def pool(self, verbs: Iterable[Verb]) -> list[Verb]:
        return [v for v in verbs if v.ending in self.endings and v.written not in self.skip]

    def form_at(self, n: int) -> Form:
        return self.forms[n % len(self.forms)]

    def answer(self, n: int, verb: Verb) -> TeForm:
        """The right answer to question `n` about `verb`."""
        return verb.form(self.form_at(n))

    def asks(self, n: int) -> str:
        """What question `n` asks for, in words."""
        return FORM_NAMES[self.form_at(n)]

    def grade(self, questions: Sequence[Verb], answers: Sequence[str]) -> list[bool]:
        return [
            self.answer(n, q).accepts(a)
            for n, (q, a) in enumerate(zip(questions, answers, strict=True))
        ]

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
GODAN = frozenset({Ending.TSU, Ending.NDE, Ending.ITE, Ending.SHITE})
VILLAGE = "undead-village"
PF_TEIRU = (
    ("読む", "よむ"),
    ("読んでいる", "よんでいる"),
    ("食べる", "たべる"),
    ("食べている", "たべている"),
)
PF_TA = (("食べる", "たべる"), ("食べた", "たべた"), ("行く", "いく"), ("行った", "いった"))
PF_NAI_RU = (("食べる", "たべる"), ("食べない", "たべない"), ("来る", "くる"), ("来ない", "こない"))
PF_NAI_U = (("書く", "かく"), ("書かない", "かかない"), ("買う", "かう"), ("買わない", "かわない"))
PF_NAKATTA = (("見る", "みる"), ("見なかった", "みなかった"), ("飲む", "のむ"),
              ("飲まなかった", "のまなかった"))  # fmt: skip
TE_RU = (("食べる", "たべる"), ("食べて", "たべて"))
TE_TSU = (("買う", "かう"), ("買って", "かって"))
TE_NDE = (("飲む", "のむ"), ("飲んで", "のんで"))
TE_ITE = (("書く", "かく"), ("書いて", "かいて"), ("行く", "いく"), ("行って", "いって"))
TE_SHITE = (("話す", "はなす"), ("話して", "はなして"))
TE_IRREGULAR = (("する", "する"), ("して", "して"), ("来る", "くる"), ("来て", "きて"))

LESSONS: dict[str, LessonSpec] = {
    s.id: s
    for s in (
        LessonSpec("te-ru", "る-verbs", TE_RU, frozenset({Ending.RU_VERB})),
        LessonSpec("te-tsu", "う・つ・る → って", TE_TSU, frozenset({Ending.TSU})),
        LessonSpec("te-nde", "む・ぶ・ぬ → んで", TE_NDE, frozenset({Ending.NDE})),
        LessonSpec("te-ite", "く・ぐ → いて・いで", TE_ITE, frozenset({Ending.ITE})),
        LessonSpec("te-shite", "す → して", TE_SHITE, frozenset({Ending.SHITE})),
        LessonSpec("te-irregular", "する and 来る", TE_IRREGULAR, frozenset({Ending.IRREGULAR})),
        LessonSpec("te-mixed", "Mixed て-form", (), ALL, size=12, min_verbs=6),
        # Undead Village: the plain forms, opened when the て-form Warden falls
        LessonSpec("pf-teiru", "〜ている: what is happening", PF_TEIRU, ALL, min_verbs=4,
                   forms=(Form.TEIRU,), region=VILLAGE, skip=frozenset({"ある", "いる"})),
        LessonSpec("pf-ta", "〜た: what already happened", PF_TA, ALL, min_verbs=4,
                   forms=(Form.TA,), region=VILLAGE),
        LessonSpec("pf-nai-ru", "〜ない: る-verbs, する and 来る", PF_NAI_RU,
                   frozenset({Ending.RU_VERB, Ending.IRREGULAR}), forms=(Form.NAI,),
                   region=VILLAGE),
        LessonSpec("pf-nai-u", "〜ない: う-verbs (う → わない)", PF_NAI_U, GODAN, min_verbs=4,
                   forms=(Form.NAI,), region=VILLAGE),
        LessonSpec("pf-nakatta", "〜なかった: what did not happen", PF_NAKATTA, ALL, min_verbs=4,
                   forms=(Form.NAKATTA,), region=VILLAGE),
        LessonSpec("pf-mixed", "Mixed plain forms", (), ALL, size=12, min_verbs=6,
                   forms=(Form.TA, Form.NAI, Form.NAKATTA, Form.TEIRU), region=VILLAGE,
                   skip=frozenset({"ある", "いる"})),
    )
}  # fmt: skip
REGION_GATES = {VILLAGE: "te-warden"}
"""A region past Firelink opens when this boss has fallen."""


def region_open(region: str, felled: Iterable[str]) -> bool:
    gate = REGION_GATES.get(region)
    return gate is None or gate in set(felled)


@dataclass(frozen=True)
class LessonOutcome:
    event_id: UUID
    at: datetime
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
            event.occurred_at,
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
    """Grades a て-form drill (the Firelink lessons); LessonSpec.grade grades any lesson."""
    return [q.te_form.accepts(a) for q, a in zip(questions, answers, strict=True)]
