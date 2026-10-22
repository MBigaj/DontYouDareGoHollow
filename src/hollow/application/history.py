"""Questions about the event log that several use cases share."""

from datetime import datetime

from hollow.application.ports import Clock, EventStore
from hollow.domain.calendar import GameCalendar


def game_start(store: EventStore, clock: Clock, calendar: GameCalendar) -> datetime:
    """The start of the first game day: the day of the first event, or today for a new game.

    Imports never reach before this moment. Replaying months of old Anki or GitHub history
    would turn every gap in it into a death.
    """
    first = min((event.occurred_at for event in store.all()), default=clock.now())
    return calendar.start_of(calendar.day_of(first))
