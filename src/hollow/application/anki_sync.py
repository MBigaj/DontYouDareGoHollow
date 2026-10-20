"""Pulls new reviews from Anki into the event log."""

from dataclasses import dataclass
from datetime import datetime, time
from typing import Protocol

from hollow.application.ports import Clock, EventStore
from hollow.domain.activities import ActivityKind
from hollow.domain.anki import AnkiReview, to_events
from hollow.domain.calendar import GameCalendar
from hollow.domain.events import Source, StudyLogged


class AnkiUnavailable(Exception):
    """Anki is closed, AnkiConnect is not installed, or it refused the request."""


class AnkiSource(Protocol):
    def reviews_since(self, after: datetime) -> list[AnkiReview]:
        """Every review strictly after `after`, across the configured decks."""
        ...


@dataclass(frozen=True)
class SyncResult:
    reviews: int
    new_cards: int

    @property
    def total(self) -> int:
        return self.reviews + self.new_cards


class AnkiSync:
    def __init__(
        self, store: EventStore, source: AnkiSource, clock: Clock, calendar: GameCalendar
    ) -> None:
        self._store = store
        self._source = source
        self._clock = clock
        self._calendar = calendar

    def run(self) -> SyncResult:
        added = self._store.append_new(to_events(self._source.reviews_since(self._cursor())))
        new_cards = sum(
            1 for e in added if isinstance(e, StudyLogged) and e.kind is ActivityKind.ANKI_NEW_CARDS
        )
        return SyncResult(reviews=len(added) - new_cards, new_cards=new_cards)

    def _cursor(self) -> datetime:
        """The newest imported review, or the start of the game for the first sync.

        History from before the game began is not imported: replaying months of old Anki
        days would turn every gap in them into a death.
        """
        events = self._store.all()
        imported = [
            e.occurred_at for e in events if isinstance(e, StudyLogged) and e.source is Source.ANKI
        ]
        if imported:
            return max(imported)
        first = min((e.occurred_at for e in events), default=self._clock.now())
        start_day = self._calendar.day_of(first)
        return datetime.combine(
            start_day, time(self._calendar.day_start_hour), tzinfo=self._calendar.timezone
        )
