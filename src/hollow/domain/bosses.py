"""Boss fights: phases, HP, Estus, wounds and rewards, replayed from fight events.

Rules (from the plan):
- Retries are immediate and unlimited. Dying sends you back to the fog gate, not to tomorrow.
- A new attempt starts at the furthest phase you have reached; cleared phases stay cleared.
- Every correct answer pays souls, even in a lost fight.
- Wounds: each death leaves the boss 10% weaker next time, down to 70% HP.
- Resting at the fog gate keeps the fight exactly where it is.
- 2 Estus flasks per attempt, 50 HP each, refilled on every retry.
- A win on the first attempt earns a bonus.
- A conversation phase (the Warden's third) has no HP bar: you reply in sentences, and the
  Sensei agent judges the replies later (agents/sensei.md). Code scores the verdict: enough
  good replies fell the boss, too few kill you, and the next attempt starts at that phase.
"""

import random
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from hollow.domain.activities import Track
from hollow.domain.architect import QUESTIONS, TOPICS, boss_id
from hollow.domain.calendar import GameCalendar
from hollow.domain.conjugation import Verb, normalize
from hollow.domain.curriculum import QuizQuestion
from hollow.domain.events import AgentResult, Event, FightAction, FightStarted, FightTurn

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
    CHOICE = "choice"
    """A quiz question from the Architect steps behind the boss: pick the right option."""
    CONVERSATION = "conversation"
    """Reply in a sentence, judged later by the Sensei: requests and sequences in context."""


@dataclass(frozen=True)
class Phase:
    name: str
    hp: int
    kinds: tuple[Kind, ...]
    seconds: int | None = None
    """Answer time limit; running out counts as a miss."""
    topics: tuple[str, ...] = ()
    """For CHOICE phases: the steps whose quiz questions the boss asks."""
    prompts: int = 0
    """For CONVERSATION phases: how many lines the boss speaks, each needing a reply."""

    @property
    def conversation(self) -> bool:
        return Kind.CONVERSATION in self.kinds


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
    region: str | None = None
    """The Architect region this boss guards; it waits until every step there is cleared."""
    home: str = "/map/firelink"
    """The map the fog gate stands on."""
    home_name: str = "Firelink"
    node: str = "warden"
    """The boss's node on its home map."""
    short: str = "Warden"
    body: str = "warden_body.png"
    weapon: str | None = None
    arena: str = "arena_bg.png"
    intro: str = ""


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
        Phase("The Warden's question", 40, (Kind.CONVERSATION,), prompts=4),
    ),
    intro="Phase 1: the て-form of your verbs against the clock. "
    "Phase 2: requests (〜てください) and sequences (〜て、〜). "
    "Phase 3: the Warden speaks; answer in sentences, and the Sensei judges them.",
)
GOLEM = Boss(
    boss_id("forge"),
    "The Strict Golem",
    Track.ARCHITECT,
    2,
    "",
    "",
    (
        Phase(
            "Craft",
            100,
            (Kind.CHOICE,),
            topics=(
                "mypy-strict-in-practice",
                "property-based-testing",
                "test-architecture",
                "packaging-and-tooling-with-uv",
            ),
        ),
        Phase(
            "The runtime beneath",
            100,
            (Kind.CHOICE,),
            seconds=45,
            topics=(
                "asyncio-internals",
                "concurrency-choices-threads-processes-async",
                "profiling-and-performance",
                "python-memory-model",
            ),
        ),
    ),
    min_verbs=0,
    region="forge",
    home="/map/architect/forge",
    home_name="the Forge",
    node="forge-boss",
    short="Golem",
    body="golem_body.png",
    weapon=None,
    arena="arena_forge.png",
    intro="Phase 1: your craft, types, tests and tooling. Phase 2: the runtime beneath, "
    "asyncio, concurrency, profiling and memory, against the clock.",
)
WYRM = Boss(
    boss_id("data-depths"),
    "The Lock Wyrm",
    Track.ARCHITECT,
    3,
    "",
    "",
    (
        Phase(
            "Held rows",
            100,
            (Kind.CHOICE,),
            topics=(
                "mvcc-and-isolation-levels",
                "locks-deadlocks-and-contention",
                "zero-downtime-migrations",
                "connection-pooling-under-load",
            ),
        ),
        Phase(
            "The planner's eye",
            100,
            (Kind.CHOICE,),
            topics=(
                "reading-query-plans",
                "index-design",
                "postgresql-vs-mongodb-modelling",
            ),
        ),
        Phase(
            "The flooded deep",
            110,
            (Kind.CHOICE,),
            seconds=45,
            topics=(
                "replication-and-read-replicas",
                "partitioning-and-sharding",
                "caching-patterns-and-invalidation",
                "redis-beyond-caching",
            ),
        ),
    ),
    min_verbs=0,
    region="data-depths",
    home="/map/architect/data-depths",
    home_name="Data Depths",
    node="data-depths-boss",
    short="Wyrm",
    body="wyrm_body.png",
    weapon=None,
    arena="arena_data_depths.png",
    intro="Phase 1: held rows, isolation, locks, migrations and pools. Phase 2: the planner's "
    "eye, plans, indexes and modelling. Phase 3: the flooded deep, replicas, shards and "
    "caches, against the clock.",
)
BOSSES = {b.id: b for b in (WARDEN, GOLEM, WYRM)}
ARCH_BOSSES = (GOLEM, WYRM)
"""The Architect road's bosses in road order, one per region with a map."""


def architect_foe(felled: set[str]) -> Boss:
    """The next Architect boss still standing (`felled` holds region ids), else the last."""
    return next((b for b in ARCH_BOSSES if b.region not in felled), ARCH_BOSSES[-1])


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


@dataclass(frozen=True)
class ChoiceQuestion:
    """A quiz question with its options shuffled for this turn."""

    question_id: str
    order: tuple[int, ...]
    """Indices into the written options, in the order they are shown."""
    kind: Kind = Kind.CHOICE

    @property
    def quiz(self) -> QuizQuestion:
        return QUESTIONS[self.question_id]

    @property
    def options(self) -> list[str]:
        return [self.quiz.options[i] for i in self.order]

    @property
    def topic(self) -> str:
        return TOPICS[self.question_id.split("#")[0]].title

    @property
    def answers(self) -> tuple[str, str]:
        """The right option and the explanation."""
        return self.quiz.options[self.quiz.answer], self.quiz.explanation

    def accepts(self, answer: str) -> bool:
        """`answer` is the position of the chosen option as shown, from 0."""
        try:
            shown = int(answer)
        except ValueError:
            return False
        return 0 <= shown < len(self.order) and self.order[shown] == self.quiz.answer


def choice(phase: Phase, seed: int, turn: int) -> ChoiceQuestion:
    """Walks a seeded shuffle of the phase's questions, so a fight rarely repeats one."""
    pool = sorted(q for t in phase.topics for q in (x.id for x in TOPICS[t].quiz))
    random.Random(f"{seed}:pool").shuffle(pool)
    asked = pool[turn % len(pool)]
    order = list(range(len(QUESTIONS[asked].options)))
    random.Random(f"{seed}:{turn}").shuffle(order)
    return ChoiceQuestion(asked, tuple(order))


PASS_REPLIES = 3
"""Good replies a conversation phase needs to fell the boss (out of its prompts)."""


def question(
    boss: Boss, phase: int, seed: int, turn: int, verbs: Sequence[Verb]
) -> Question | ChoiceQuestion:
    """The question for one turn of an attempt; the same seed and turn always ask the same.
    In a conversation phase it is the line the boss speaks: a request (ask me to...) or a
    sequence (tell me what you do, then...), answered in a whole sentence."""
    if Kind.CHOICE in boss.phases[phase].kinds:
        return choice(boss.phases[phase], seed, turn)
    rng = random.Random(f"{seed}:{turn}")
    kinds = boss.phases[phase].kinds
    if boss.phases[phase].conversation:
        kinds = (Kind.REQUEST, Kind.SEQUENCE)
    kind = kinds[turn % len(kinds)]
    pool = [v for v in verbs if v.written != "する"] or list(verbs)
    if kind is Kind.SEQUENCE:
        first, second = rng.sample(pool, 2)
        return Question(kind, (first, second))
    return Question(kind, (rng.choice(pool if kind is Kind.REQUEST else list(verbs)),))


def _gloss(verb: Verb) -> str:
    """A verb's meaning as the Warden's lines use it: 'to open (a door)' becomes 'open'."""
    meaning = verb.meaning.split(";")[0].split(",")[0].strip()
    meaning = meaning.removeprefix("to ").split(" (")[0].strip()
    return meaning or verb.kana


def spoken(line: Question) -> str:
    """What the boss says in a conversation phase, in English: the reply must be Japanese.
    A request wants 〜てください in a sentence, a sequence wants 〜て、〜."""
    first = line.verbs[0]
    if line.kind is Kind.REQUEST or len(line.verbs) < 2:
        return f"Ask me, politely, to {_gloss(first)} ({first.written})."
    second = line.verbs[1]
    return (f"Tell me what you do: first you {_gloss(first)} ({first.written}), "
            f"then you {_gloss(second)} ({second.written}).")  # fmt: skip


RUBRIC = (
    "A reply is good when it is one Japanese sentence that does what the line asks with its "
    "verbs: a request ends in 〜てください, a sequence joins the two actions with the first "
    "verb's て-form (〜て、〜). Wrong て-forms are not good; slips in other words are."
)
"""What the Sensei judges each reply on; the game then counts the good ones."""


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
    REPLY = "reply"
    """A reply given in a conversation phase."""
    JUDGING = "judging"
    """Every line answered: the fight waits for the Sensei's verdict."""


@dataclass(frozen=True)
class Attempt:
    id: UUID
    boss_id: str
    started_on: date
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
    flasks: int = ESTUS_FLASKS
    """Estus flasks the attempt began with (armour can add one)."""
    phases: int = 0
    """How many of the boss's phases this attempt has (FightStarted.phases)."""
    replies: tuple[str, ...] = ()
    """Your replies in the current conversation phase, in order."""
    prompts: int = 0
    """Lines the current conversation phase speaks; 0 outside one."""

    @property
    def conversing(self) -> bool:
        return self.prompts > 0

    @property
    def judging(self) -> bool:
        """Every line answered; the attempt waits for the Sensei's verdict."""
        return (
            self.outcome is Outcome.ACTIVE and self.conversing and len(self.replies) >= self.prompts
        )

    @property
    def can_drink(self) -> bool:
        return (
            self.outcome is Outcome.ACTIVE
            and not self.conversing
            and self.estus > 0
            and self.hp < self.max_hp
        )


@dataclass(frozen=True)
class Reward:
    day: date
    souls: int
    lights: bool = False


@dataclass(frozen=True)
class TurnLog:
    """One answered turn: enough to rebuild the question that was asked."""

    at: datetime
    seed: int
    phase: int
    turn: int
    correct: bool


@dataclass
class BossRecord:
    boss: Boss
    attempts: list[Attempt] = field(default_factory=list)
    rewards: list[Reward] = field(default_factory=list)
    defeated_at: datetime | None = None
    log: list[TurnLog] = field(default_factory=list)

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


def start(record: BossRecord, event: FightStarted, day: date) -> Attempt:
    wound = record.next_wound
    phases = min(event.phases or len(record.boss.phases), len(record.boss.phases))
    phase = min(record.furthest_phase, phases - 1) if not record.defeated else 0
    hp = phase_hp(record.boss, phase, wound)
    return Attempt(
        id=event.id,
        boss_id=record.boss.id,
        started_on=day,
        number=len([a for a in record.attempts if a.outcome is not Outcome.ABANDONED]) + 1,
        seed=event.seed,
        phase=phase,
        boss_hp=hp,
        boss_max_hp=hp,
        hp=event.max_hp,
        max_hp=event.max_hp,
        mistake_cost=event.mistake_cost,
        damage=event.damage,
        estus=event.estus,
        wound=wound,
        flasks=event.estus,
        phases=phases,
        prompts=record.boss.phases[phase].prompts,
    )


def play(boss: Boss, attempt: Attempt, turn: FightTurn) -> Attempt:
    """Applies one turn. Turns that cannot happen (a sip with no flasks) change nothing."""
    if attempt.outcome is not Outcome.ACTIVE:
        return attempt
    if attempt.conversing:  # only replies count here, until every line is answered
        if turn.action is not FightAction.REPLY or attempt.judging:
            return attempt
        replies = (*attempt.replies, turn.text)
        beat = Beat.JUDGING if len(replies) >= attempt.prompts else Beat.REPLY
        return replace(attempt, replies=replies, turns=attempt.turns + 1, beat=beat,
                       last_correct=None)  # fmt: skip
    if turn.action is FightAction.REPLY:
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
    if attempt.phase + 1 < (attempt.phases or len(boss.phases)):
        nxt = attempt.phase + 1
        hp = phase_hp(boss, nxt, attempt.wound)
        return replace(attempt, phase=nxt, boss_hp=hp, boss_max_hp=hp, beat=Beat.PHASE,
                       prompts=boss.phases[nxt].prompts)  # fmt: skip
    return replace(attempt, boss_hp=0, outcome=Outcome.WON, beat=Beat.WON)


def verdict_task(attempt: Attempt) -> str:
    """The Sensei's task id for an attempt's conversation phase."""
    return f"boss:{attempt.boss_id}:{attempt.id}:phase-{attempt.phase + 1}"


def judge(attempt: Attempt, good: Sequence[bool]) -> Attempt:
    """Applies the Sensei's verdict on each reply. Code decides: PASS_REPLIES good replies
    fell the boss; fewer, and the boss strikes you down (retry at this phase)."""
    if not attempt.judging or len(good) != len(attempt.replies):
        return attempt
    hits = sum(good)
    if hits >= min(PASS_REPLIES, attempt.prompts):
        return replace(attempt, hits=attempt.hits + hits, boss_hp=0, outcome=Outcome.WON,
                       beat=Beat.WON)  # fmt: skip
    return replace(attempt, hits=attempt.hits + hits, misses=attempt.misses + len(good) - hits,
                   hp=0, outcome=Outcome.DIED, beat=Beat.DIED)  # fmt: skip


def track(events: Iterable[Event], calendar: GameCalendar, today: date) -> dict[str, BossRecord]:
    records = {boss_id: BossRecord(boss) for boss_id, boss in BOSSES.items()}
    by_attempt: dict[UUID, str] = {}
    for event in sorted(
        (e for e in events if isinstance(e, FightStarted | FightTurn | AgentResult)),
        key=lambda e: e.occurred_at,
    ):
        day = calendar.day_of(event.occurred_at)
        if day > today:
            continue
        if isinstance(event, AgentResult):
            verdict(records, event, day)
            continue
        if isinstance(event, FightStarted):
            record = records.get(event.boss_id)
            if record is None:
                continue
            if record.current is not None:
                record.attempts[-1] = replace(record.attempts[-1], outcome=Outcome.ABANDONED)
            record.attempts.append(start(record, event, day))
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
        if event.action is FightAction.ANSWER:
            record.log.append(
                TurnLog(
                    event.occurred_at, current.seed, current.phase, current.turns, event.correct
                )
            )
        after = play(record.boss, current, event)
        record.attempts[-1] = after
        if after.hits > current.hits:
            record.rewards.append(Reward(day, SOULS_PER_HIT))
        if after.outcome is Outcome.WON and first_win:
            record.defeated_at = event.occurred_at
            bonus = FIRST_TRY_BONUS if after.number == 1 else 0
            record.rewards.append(Reward(day, VICTORY_SOULS + bonus, lights=True))
    return records


def verdict(records: dict[str, BossRecord], event: AgentResult, day: date) -> None:
    """A Sensei verdict on a conversation phase: applied to the attempt it names, if that
    attempt is still waiting for it (the app validated it on submit)."""
    if event.agent != "sensei" or not event.task.startswith("boss:"):
        return
    record = records.get(event.task.split(":")[1])
    current = record.current if record else None
    if record is None or current is None or verdict_task(current) != event.task:
        return
    turns = event.payload.get("turns", [])
    good = [bool(t.get("ok")) for t in turns if isinstance(t, dict)]
    first_win = not record.defeated
    after = judge(current, good)
    if after is current:
        return
    record.attempts[-1] = after
    for _ in range(after.hits - current.hits):
        record.rewards.append(Reward(day, SOULS_PER_HIT))
    if after.outcome is Outcome.WON and first_win:
        record.defeated_at = event.occurred_at
        bonus = FIRST_TRY_BONUS if after.number == 1 else 0
        record.rewards.append(Reward(day, VICTORY_SOULS + bonus, lights=True))


def lines(boss: Boss, attempt: Attempt, verbs: Sequence[Verb]) -> list[Question]:
    """Every line the boss speaks in an attempt's conversation phase, in order."""
    if not attempt.conversing:
        return []
    asked = [question(boss, attempt.phase, attempt.seed, n, verbs) for n in range(attempt.prompts)]
    return [q for q in asked if isinstance(q, Question)]
