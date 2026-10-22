from hollow.application.ports import Clock, EventStore
from hollow.domain.activities import LIGHT_THE_BONFIRE, ActivityKind
from hollow.domain.calendar import GameCalendar
from hollow.domain.events import MessageLeft, StatLevelled, StudyLogged
from hollow.domain.progression import STAT_MAX, Stat
from hollow.domain.world import WorldState, replay

MAX_QUANTITY = 10_000
MAX_TEXT = 280


class CannotLevelUp(Exception):
    """Not enough souls, or the stat is already at its maximum."""


class BonfireService:
    def __init__(self, store: EventStore, clock: Clock, calendar: GameCalendar) -> None:
        self._store = store
        self._clock = clock
        self._calendar = calendar

    def state(self) -> WorldState:
        today = self._calendar.day_of(self._clock.now())
        return replay(self._store.all(), self._calendar, today)

    def light(self) -> WorldState:
        """The one-tap daily minimum: logs the kindling amount of Anki reviews."""
        kind, quantity = LIGHT_THE_BONFIRE
        return self.log_study(kind, quantity, note="Lit the bonfire")

    def log_study(self, kind: ActivityKind, quantity: int, note: str = "") -> WorldState:
        if not 0 < quantity <= MAX_QUANTITY:
            raise ValueError(f"quantity must be between 1 and {MAX_QUANTITY}")
        self._store.append(StudyLogged(self._clock.now(), kind, quantity, note[:MAX_TEXT]))
        return self.state()

    def leave_message(self, text: str) -> WorldState:
        self._store.append(MessageLeft(self._clock.now(), text[:MAX_TEXT]))
        return self.state()

    def level_up(self, stat: Stat) -> WorldState:
        """Spends souls at the bonfire to raise one stat by one level."""
        state = self.state()
        if state.stats[stat] >= STAT_MAX:
            raise CannotLevelUp(f"{stat.value.title()} is already at {STAT_MAX}.")
        if not state.can_level_up:
            missing = state.level_cost - state.souls
            raise CannotLevelUp(f"You need {missing:,} more souls.")
        self._store.append(StatLevelled(self._clock.now(), stat, state.level_cost))
        return self.state()
