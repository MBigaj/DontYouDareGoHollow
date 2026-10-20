from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Protocol

from hollow.domain.events import Event


class EventStore(Protocol):
    def append(self, event: Event) -> None: ...

    def append_new(self, events: Sequence[Event]) -> list[Event]:
        """Appends only the events whose ids are not stored yet, and returns those."""
        ...

    def all(self) -> Sequence[Event]: ...


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)
