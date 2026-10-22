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


Event = StudyLogged | MessageLeft | StatLevelled
