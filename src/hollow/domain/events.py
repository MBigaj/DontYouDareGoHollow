"""The event log is the source of truth: souls, bloodstains and hollowing derive from it."""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from hollow.domain.activities import ActivityKind


@dataclass(frozen=True)
class StudyLogged:
    occurred_at: datetime
    kind: ActivityKind
    quantity: int
    note: str = ""
    id: UUID = field(default_factory=uuid4)

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


Event = StudyLogged | MessageLeft
