"""Running boss fights. Every turn is an event, so a fight survives restarts and resting."""

from dataclasses import dataclass
from datetime import datetime
from random import SystemRandom
from uuid import UUID

from hollow.application.lessons import LessonError
from hollow.application.ports import Clock, EventStore, next_moment
from hollow.domain.bosses import (
    BOSSES,
    Attempt,
    Boss,
    BossRecord,
    ChoiceQuestion,
    Question,
    lines,
    question,
)
from hollow.domain.calendar import GameCalendar
from hollow.domain.conjugation import Verb
from hollow.domain.events import FightAction, FightStarted, FightTurn
from hollow.domain.lessons import LESSONS
from hollow.domain.vocabulary import known_verbs
from hollow.domain.world import WorldState, replay

REPLY_LIMIT = 120
"""A reply is one sentence; the Sensei's result shape allows 200 characters."""


class FightError(LessonError):
    """An unknown boss, too few verbs, or a turn for a fight that is not on."""


@dataclass(frozen=True)
class Answered:
    question: Question | ChoiceQuestion
    given: str
    correct: bool


@dataclass(frozen=True)
class FightView:
    boss: Boss
    record: BossRecord
    state: WorldState
    question: Question | ChoiceQuestion | None
    """The question waiting for an answer, when a fight is on."""
    answered: Answered | None = None

    @property
    def attempt(self) -> Attempt | None:
        return self.record.current or self.record.last


class FightService:
    def __init__(self, store: EventStore, clock: Clock, calendar: GameCalendar) -> None:
        self._store = store
        self._clock = clock
        self._calendar = calendar

    def _now(self) -> datetime:
        """Now, but after the last event, so turns replay in the order they were played."""
        return next_moment(self._store, self._clock)

    def boss(self, boss_id: str) -> Boss:
        try:
            return BOSSES[boss_id]
        except KeyError:
            raise FightError(f"There is no boss called {boss_id}.") from None

    def verbs(self) -> list[Verb]:
        return known_verbs(self._store.all())

    def view(self, boss_id: str, answered: Answered | None = None) -> FightView:
        boss = self.boss(boss_id)
        today = self._calendar.day_of(self._clock.now())
        state = replay(self._store.all(), self._calendar, today)
        record = state.bosses[boss.id]
        current = record.current
        ask = None
        if current is not None and not current.judging:
            turn = len(current.replies) if current.conversing else current.turns
            ask = question(boss, current.phase, current.seed, turn, self.verbs())
        return FightView(boss, record, state, ask, answered)

    def transcript(self, boss_id: str) -> list[tuple[Question, str]]:
        """The current conversation phase so far: each line the boss spoke and your reply."""
        view = self.view(boss_id)
        current = view.record.current
        if current is None:
            return []
        return list(zip(lines(view.boss, current, self.verbs()), current.replies, strict=False))

    @staticmethod
    def damage(boss: Boss, state: WorldState) -> int:
        """Your equipped weapon's damage against this boss."""
        weapon, level = state.armory.weapon(boss.track)
        return weapon.damage(level, boss.recommended)

    def ready(self, boss_id: str) -> bool:
        boss = self.boss(boss_id)
        if boss.region is not None:
            today = self._calendar.day_of(self._clock.now())
            state = replay(self._store.all(), self._calendar, today)
            return state.architect.region_ready(boss.region)
        if boss.lessons_region is not None:
            return self.cleared_in(boss.lessons_region) >= boss.clears
        return len(self.verbs()) >= boss.min_verbs

    def cleared_in(self, region: str) -> int:
        """Lessons of a Ronin region cleared so far."""
        today = self._calendar.day_of(self._clock.now())
        state = replay(self._store.all(), self._calendar, today)
        return sum(
            1
            for spec in LESSONS.values()
            if spec.region == region and (p := state.lessons.get(spec.id)) and p.cleared
        )

    def requirement(self, boss_id: str) -> str:
        """What opens the fog, in words."""
        boss = self.boss(boss_id)
        if boss.region is not None:
            return f"The fog will not part until every step of {boss.home_name} is cleared."
        if boss.lessons_region is not None:
            return (
                f"The fog will not part until you clear {boss.clears} {boss.home_name} lessons "
                f"({self.cleared_in(boss.lessons_region)} so far)."
            )
        return f"The fog will not part until you know {boss.min_verbs} verbs."

    def enter(self, boss_id: str) -> FightView:
        """Steps through the fog: resumes the fight that is on, or starts a new attempt."""
        view = self.view(boss_id)
        if view.record.current is not None:
            return view
        if not self.ready(boss_id):
            raise FightError(self.requirement(boss_id))
        self._store.append(
            FightStarted(
                self._now(),
                view.boss.id,
                SystemRandom().randrange(2**32),
                view.state.max_hp,
                view.state.mistake_cost,
                self.damage(view.boss, view.state),
                view.state.estus,
                len(view.boss.phases),
                view.state.souls_per_hit,
            )
        )
        return self.view(boss_id)

    def _current(self, boss_id: str, attempt_id: str) -> FightView:
        view = self.view(boss_id)
        current = view.record.current
        if current is None or str(current.id) != attempt_id:
            raise FightError("That fight is over. Step through the fog again.")
        return view

    def answer(self, boss_id: str, attempt_id: str, turn: int, given: str) -> FightView:
        view = self._current(boss_id, attempt_id)
        current, ask = view.record.current, view.question
        assert current is not None
        if ask is None or current.conversing or turn != current.turns:
            return view  # a double submit, or a conversation (answered with reply())
        correct = ask.accepts(given)
        self._store.append(FightTurn(self._now(), UUID(attempt_id), FightAction.ANSWER, correct))
        return self.view(boss_id, Answered(ask, given.strip()[:40], correct))

    def reply(self, boss_id: str, attempt_id: str, turn: int, text: str) -> FightView:
        """One reply in a conversation phase. It is judged later, by the Sensei."""
        view = self._current(boss_id, attempt_id)
        current = view.record.current
        assert current is not None
        if not current.conversing or current.judging or turn != len(current.replies):
            return view  # not a conversation, already answered, or a double submit
        text = " ".join(text.split())
        if not text:
            raise FightError("Answer the Warden in Japanese: a whole sentence.")
        if len(text) > REPLY_LIMIT:
            raise FightError(f"Keep it to one sentence ({REPLY_LIMIT} characters at most).")
        self._store.append(FightTurn(self._now(), UUID(attempt_id), FightAction.REPLY, text=text))
        return self.view(boss_id)

    def drink(self, boss_id: str, attempt_id: str) -> FightView:
        view = self._current(boss_id, attempt_id)
        current = view.record.current
        assert current is not None
        if not current.can_drink:
            return view
        self._store.append(FightTurn(self._now(), UUID(attempt_id), FightAction.ESTUS))
        return self.view(boss_id)
