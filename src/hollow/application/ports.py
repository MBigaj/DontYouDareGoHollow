from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
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


def next_moment(store: EventStore, clock: Clock) -> datetime:
    """Now, but always after the newest stored event.

    Replays sort by time, so actions taken in quick succession (buy, then reinforce, then
    equip) must never share a timestamp, or they could replay out of order.
    """
    now = clock.now()
    events = store.all()
    newest = events[-1].occurred_at if events else None
    if newest is not None and newest >= now:
        return newest + timedelta(microseconds=1)
    return now
