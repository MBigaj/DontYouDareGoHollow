"""The event log is the source of truth: souls, bloodstains and hollowing derive from it."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from hollow.domain.activities import ActivityKind
from hollow.domain.progression import Stat


class Source(StrEnum):
    MANUAL = "manual"
    ANKI = "anki"
    GITHUB = "github"


@dataclass(frozen=True)
class StudyLogged:
    occurred_at: datetime
    kind: ActivityKind
    quantity: int
    note: str = ""
    source: Source = Source.MANUAL
    id: UUID = field(default_factory=uuid4)
    """Imported events get a deterministic id, so importing the same thing twice is a no-op."""

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValueError("quantity must be positive")
        if self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware")


@dataclass(frozen=True)
class MessageLeft:
    """A note left at the bonfire for tomorrow's you."""

    occurred_at: datetime
    text: str
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("a message cannot be empty")
        if self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware")


@dataclass(frozen=True)
class StatLevelled:
    """Souls spent at the bonfire to raise a stat by one level.

    The price is recorded, so retuning the cost curve never changes past purchases.
    """

    occurred_at: datetime
    stat: Stat
    cost: int
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if self.cost < 0:
            raise ValueError("cost cannot be negative")
        if self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware")


@dataclass(frozen=True)
class WordLearned:
    """A card you have studied in Anki. Drills and agent texts only use words you know."""

    occurred_at: datetime
    note_id: int
    written: str
    kana: str
    meaning: str
    part_of_speech: str
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not self.written.strip():
            raise ValueError("a word cannot be empty")
        if self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware")


@dataclass(frozen=True)
class LessonCompleted:
    """One finished run through a lesson. Souls and refresher timing replay from these."""

    occurred_at: datetime
    lesson_id: str
    correct: int
    total: int
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if not 0 <= self.correct <= self.total or self.total <= 0:
            raise ValueError("correct must be between 0 and a positive total")
        if self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware")

    @property
    def score(self) -> float:
        return self.correct / self.total


class FightAction(StrEnum):
    ANSWER = "answer"
    ESTUS = "estus"


@dataclass(frozen=True)
class FightStarted:
    """You stepped through a boss's fog gate. A new attempt, with a seed for its questions."""

    occurred_at: datetime
    boss_id: str
    seed: int
    max_hp: int
    mistake_cost: int
    """Your Vigor and Endurance when the attempt began, so levelling later never rewrites it."""
    damage: int = 10
    """Your weapon's damage against this boss when the attempt began."""
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware")


@dataclass(frozen=True)
class FightTurn:
    """One answer (right or wrong) or one Estus sip in a fight."""

    occurred_at: datetime
    attempt_id: UUID
    action: FightAction
    correct: bool = False
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware")


class Material(StrEnum):
    SHARD = "titanite_shard"
    LARGE_SHARD = "large_titanite_shard"
    CHUNK = "titanite_chunk"
    SLAB = "titanite_slab"


@dataclass(frozen=True)
class MaterialDropped:
    """A random drop, saved when it was rolled so replays and retuned odds never change it."""

    occurred_at: datetime
    material: Material
    count: int
    source: str
    """What dropped it, e.g. "lesson:<run id>"."""
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if self.count <= 0:
            raise ValueError("count must be positive")
        if self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware")


@dataclass(frozen=True)
class WeaponBought:
    occurred_at: datetime
    weapon_id: str
    cost: int
    id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class WeaponUpgraded:
    """Souls and titanite spent at the blacksmith. Prices are recorded, like stat levels."""

    occurred_at: datetime
    weapon_id: str
    level: int
    """The level reached."""
    cost: int
    material: Material
    material_count: int
    id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class WeaponEquipped:
    occurred_at: datetime
    weapon_id: str
    id: UUID = field(default_factory=uuid4)


Event = (
    StudyLogged
    | MessageLeft
    | StatLevelled
    | WordLearned
    | LessonCompleted
    | FightStarted
    | FightTurn
    | MaterialDropped
    | WeaponBought
    | WeaponUpgraded
    | WeaponEquipped
)
