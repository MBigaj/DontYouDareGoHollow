"""The blacksmith: buy basic weapons, reinforce them with souls and titanite, equip them."""

from hollow.application.ports import Clock, EventStore, next_moment
from hollow.domain.armory import MATERIAL_NAMES, WEAPONS, WeaponSpec, upgrade_cost
from hollow.domain.calendar import GameCalendar
from hollow.domain.events import WeaponBought, WeaponEquipped, WeaponUpgraded
from hollow.domain.world import WorldState, replay


class BlacksmithError(ValueError):
    """Not enough souls or titanite, or a weapon you cannot buy, reinforce or wield."""


class Blacksmith:
    def __init__(self, store: EventStore, clock: Clock, calendar: GameCalendar) -> None:
        self._store = store
        self._clock = clock
        self._calendar = calendar

    def state(self) -> WorldState:
        return replay(
            self._store.all(),
            self._calendar,
            self._calendar.day_of(next_moment(self._store, self._clock)),
        )

    @staticmethod
    def spec(weapon_id: str) -> WeaponSpec:
        try:
            return WEAPONS[weapon_id]
        except KeyError:
            raise BlacksmithError(f"The blacksmith has never heard of {weapon_id}.") from None

    def buy(self, weapon_id: str) -> WorldState:
        spec, state = self.spec(weapon_id), self.state()
        if state.armory.owns(weapon_id):
            raise BlacksmithError(f"You already own the {spec.name}.")
        if not spec.price:
            raise BlacksmithError(f"The {spec.name} is not for sale.")
        if state.souls < spec.price:
            raise BlacksmithError(f"You need {spec.price - state.souls:,} more souls.")
        self._store.append(
            WeaponBought(next_moment(self._store, self._clock), weapon_id, spec.price)
        )
        return self.state()

    def upgrade(self, weapon_id: str) -> WorldState:
        spec, state = self.spec(weapon_id), self.state()
        if not state.armory.owns(weapon_id):
            raise BlacksmithError(f"You do not own the {spec.name}.")
        level = state.armory.levels[weapon_id]
        if level >= spec.max_level:
            raise BlacksmithError(f"The {spec.name} is already at +{spec.max_level}.")
        souls, material, count = upgrade_cost(level + 1)
        if state.souls < souls:
            raise BlacksmithError(f"You need {souls - state.souls:,} more souls.")
        if state.armory.materials[material] < count:
            missing = count - state.armory.materials[material]
            raise BlacksmithError(f"You need {missing} more {MATERIAL_NAMES[material]}.")
        self._store.append(
            WeaponUpgraded(
                next_moment(self._store, self._clock), weapon_id, level + 1, souls, material, count
            )
        )
        return self.state()

    def equip(self, weapon_id: str) -> WorldState:
        spec, state = self.spec(weapon_id), self.state()
        if not state.armory.owns(weapon_id):
            raise BlacksmithError(f"You do not own the {spec.name}.")
        self._store.append(WeaponEquipped(next_moment(self._store, self._clock), weapon_id))
        return self.state()
