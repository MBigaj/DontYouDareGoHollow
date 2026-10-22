"""Pulls new reviews from Anki into the event log."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from hollow.application.history import game_start
from hollow.application.ports import Clock, EventStore
from hollow.domain.activities import ActivityKind
from hollow.domain.anki import AnkiReview, to_events
from hollow.domain.calendar import GameCalendar
from hollow.domain.events import Source, StudyLogged

LOOKBACK = timedelta(days=3)
"""How far before the newest imported review each sync looks again.

Reviews done on a phone reach desktop Anki only when it syncs with AnkiWeb, so they can
arrive after newer ones were imported. Imports are idempotent, so re-reading is safe.
"""


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
        """A few days before the newest imported review, but never before the game began.

        History from before the game began is not imported: replaying months of old Anki
        days would turn every gap in them into a death.
        """
        start = game_start(self._store, self._clock, self._calendar)
        imported = [
            e.occurred_at
            for e in self._store.all()
            if isinstance(e, StudyLogged) and e.source is Source.ANKI
        ]
        if not imported:
            return start
        return max(start, max(imported) - LOOKBACK)
