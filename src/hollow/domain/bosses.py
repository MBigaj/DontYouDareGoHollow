"""Boss fights: phases, HP, Estus, wounds and rewards, replayed from fight events.

Rules (from the plan):
- Retries are immediate and unlimited. Dying sends you back to the fog gate, not to tomorrow.
- A new attempt starts at the furthest phase you have reached; cleared phases stay cleared.
- Every correct answer pays souls, even in a lost fight.
- Wounds: each death leaves the boss 10% weaker next time, down to 70% HP.
- Resting at the fog gate keeps the fight exactly where it is.
- 2 Estus flasks per attempt, 50 HP each, refilled on every retry.
- A win on the first attempt earns a bonus.
"""

import random
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from hollow.domain.activities import Track
from hollow.domain.calendar import GameCalendar
from hollow.domain.conjugation import Verb, normalize
from hollow.domain.events import Event, FightAction, FightStarted, FightTurn

DAMAGE = 10
ESTUS_FLASKS = 2
ESTUS_HEAL = 50
WOUND_STEP = 0.1
WOUND_FLOOR = 0.7
SOULS_PER_HIT = 5
VICTORY_SOULS = 500
FIRST_TRY_BONUS = 250


class Kind(StrEnum):
    TE = "te"
    """Dictionary form → て-form."""
    REQUEST = "request"
    """Ask politely: 〜てください."""
    SEQUENCE = "sequence"
    """Two actions in order: 〜て、〜."""


@dataclass(frozen=True)
class Phase:
    name: str
    hp: int
    kinds: tuple[Kind, ...]
    seconds: int | None = None
    """Answer time limit; running out counts as a miss."""


@dataclass(frozen=True)
class Boss:
    id: str
    name: str
    track: Track
    recommended: int
    """The weapon level the fight is tuned for; levels above it count half."""
    jp: str
    jp_kana: str
    phases: tuple[Phase, ...]
    min_verbs: int = 6


WARDEN = Boss(
    "te-warden",
    "The て-form Warden",
    Track.RONIN,
    2,
    "て形の番人",
    "てけいのばんにん",
    (
        Phase("Swift conjugation", 120, (Kind.TE,), seconds=20),
        Phase("Requests and sequences", 80, (Kind.REQUEST, Kind.SEQUENCE)),
    ),
)
BOSSES = {WARDEN.id: WARDEN}


@dataclass(frozen=True)
class Question:
    kind: Kind
    verbs: tuple[Verb, ...]

    @property
    def answers(self) -> tuple[str, str]:
        """The written answer and its kana."""
        first = self.verbs[0].te_form
        if self.kind is Kind.TE:
            return first.written, first.kana
        if self.kind is Kind.REQUEST:
            return first.written + "ください", first.kana + "ください"
        second = self.verbs[1]
        return f"{first.written}、{second.written}", f"{first.kana}、{second.kana}"

    def accepts(self, answer: str) -> bool:
        # normalize (NFKC) turns a full-width comma into ","; both mean 、 here
        given = normalize(answer).replace("下さい", "ください").replace(",", "、")
        first = self.verbs[0].te_form
        heads = {normalize(first.written), normalize(first.kana)}
        if self.kind is Kind.TE:
            return given in heads
        if self.kind is Kind.REQUEST:
            return given in {h + "ください" for h in heads}
        tails = {normalize(self.verbs[1].written), normalize(self.verbs[1].kana)}
        return any(given in {h + t, h + "、" + t} for h in heads for t in tails)


def question(boss: Boss, phase: int, seed: int, turn: int, verbs: Sequence[Verb]) -> Question:
    """The question for one turn of an attempt; the same seed and turn always ask the same."""
    rng = random.Random(f"{seed}:{turn}")
    kinds = boss.phases[phase].kinds
    kind = kinds[turn % len(kinds)]
    pool = [v for v in verbs if v.written != "する"] or list(verbs)
    if kind is Kind.SEQUENCE:
        first, second = rng.sample(pool, 2)
        return Question(kind, (first, second))
    return Question(kind, (rng.choice(pool if kind is Kind.REQUEST else list(verbs)),))


class Outcome(StrEnum):
    ACTIVE = "active"
    DIED = "died"
    WON = "won"
    ABANDONED = "abandoned"


class Beat(StrEnum):
    """What the last turn did, so the page can animate it."""

    START = "start"
    HIT = "hit"
    MISS = "miss"
    ESTUS = "estus"
    PHASE = "phase"
    DIED = "died"
    WON = "won"


@dataclass(frozen=True)
class Attempt:
    id: UUID
    number: int
    seed: int
    phase: int
    boss_hp: int
    boss_max_hp: int
    hp: int
    max_hp: int
    mistake_cost: int
    damage: int
    estus: int
    wound: float
    """Boss HP multiplier from earlier deaths (1.0 down to 0.7)."""
    turns: int = 0
    """Answers given so far; picks the next question."""
    hits: int = 0
    misses: int = 0
    outcome: Outcome = Outcome.ACTIVE
    beat: Beat = Beat.START
    last_correct: bool | None = None

    @property
    def can_drink(self) -> bool:
        return self.outcome is Outcome.ACTIVE and self.estus > 0 and self.hp < self.max_hp


@dataclass(frozen=True)
class Reward:
    day: date
    souls: int
    lights: bool = False


@dataclass
class BossRecord:
    boss: Boss
    attempts: list[Attempt] = field(default_factory=list)
    rewards: list[Reward] = field(default_factory=list)
    defeated_at: datetime | None = None

    @property
    def current(self) -> Attempt | None:
        if self.attempts and self.attempts[-1].outcome is Outcome.ACTIVE:
            return self.attempts[-1]
        return None

    @property
    def last(self) -> Attempt | None:
        return self.attempts[-1] if self.attempts else None

    @property
    def defeated(self) -> bool:
        return any(a.outcome is Outcome.WON for a in self.attempts)

    @property
    def deaths(self) -> int:
        return sum(1 for a in self.attempts if a.outcome is Outcome.DIED)

    @property
    def furthest_phase(self) -> int:
        return max((a.phase for a in self.attempts), default=0)

    @property
    def next_wound(self) -> float:
        return max(WOUND_FLOOR, 1 - WOUND_STEP * self.deaths)


def phase_hp(boss: Boss, phase: int, wound: float) -> int:
    return max(DAMAGE, round(boss.phases[phase].hp * wound))


def start(record: BossRecord, event: FightStarted) -> Attempt:
    wound = record.next_wound
    phase = record.furthest_phase if not record.defeated else 0
    hp = phase_hp(record.boss, phase, wound)
    return Attempt(
        id=event.id,
        number=len([a for a in record.attempts if a.outcome is not Outcome.ABANDONED]) + 1,
        seed=event.seed,
        phase=phase,
        boss_hp=hp,
        boss_max_hp=hp,
        hp=event.max_hp,
        max_hp=event.max_hp,
        mistake_cost=event.mistake_cost,
        damage=event.damage,
        estus=ESTUS_FLASKS,
        wound=wound,
    )


def play(boss: Boss, attempt: Attempt, turn: FightTurn) -> Attempt:
    """Applies one turn. Turns that cannot happen (a sip with no flasks) change nothing."""
    if attempt.outcome is not Outcome.ACTIVE:
        return attempt
    if turn.action is FightAction.ESTUS:
        if not attempt.can_drink:
            return attempt
        return replace(
            attempt,
            hp=min(attempt.max_hp, attempt.hp + ESTUS_HEAL),
            estus=attempt.estus - 1,
            beat=Beat.ESTUS,
            last_correct=None,
        )
    attempt = replace(attempt, turns=attempt.turns + 1, last_correct=turn.correct)
    if not turn.correct:
        hp = attempt.hp - attempt.mistake_cost
        if hp <= 0:
            return replace(attempt, hp=0, misses=attempt.misses + 1, outcome=Outcome.DIED,
                           beat=Beat.DIED)  # fmt: skip
        return replace(attempt, hp=hp, misses=attempt.misses + 1, beat=Beat.MISS)
    attempt = replace(attempt, hits=attempt.hits + 1, boss_hp=attempt.boss_hp - attempt.damage,
                      beat=Beat.HIT)  # fmt: skip
    if attempt.boss_hp > 0:
        return attempt
    if attempt.phase + 1 < len(boss.phases):
        hp = phase_hp(boss, attempt.phase + 1, attempt.wound)
        return replace(attempt, phase=attempt.phase + 1, boss_hp=hp, boss_max_hp=hp,
                       beat=Beat.PHASE)  # fmt: skip
    return replace(attempt, boss_hp=0, outcome=Outcome.WON, beat=Beat.WON)


def track(events: Iterable[Event], calendar: GameCalendar, today: date) -> dict[str, BossRecord]:
    records = {boss_id: BossRecord(boss) for boss_id, boss in BOSSES.items()}
    by_attempt: dict[UUID, str] = {}
    for event in sorted(
        (e for e in events if isinstance(e, FightStarted | FightTurn)), key=lambda e: e.occurred_at
    ):
        day = calendar.day_of(event.occurred_at)
        if day > today:
            continue
        if isinstance(event, FightStarted):
            record = records.get(event.boss_id)
            if record is None:
                continue
            if record.current is not None:
                record.attempts[-1] = replace(record.attempts[-1], outcome=Outcome.ABANDONED)
            record.attempts.append(start(record, event))
            by_attempt[event.id] = event.boss_id
            continue
        boss_id = by_attempt.get(event.attempt_id)
        if boss_id is None:
            continue
        record = records[boss_id]
        current = record.current
        if current is None or current.id != event.attempt_id:
            continue
        first_win = not record.defeated
        after = play(record.boss, current, event)
        record.attempts[-1] = after
        if after.hits > current.hits:
            record.rewards.append(Reward(day, SOULS_PER_HIT))
        if after.outcome is Outcome.WON and first_win:
            record.defeated_at = event.occurred_at
            bonus = FIRST_TRY_BONUS if after.number == 1 else 0
            record.rewards.append(Reward(day, VICTORY_SOULS + bonus, lights=True))
    return records
