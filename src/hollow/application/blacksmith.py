"""The blacksmith: buy basic weapons and armour, reinforce weapons with souls and titanite, and
equip both."""

from hollow.application.ports import Clock, EventStore, next_moment
from hollow.domain.armory import (
    ARMOUR,
    MATERIAL_NAMES,
    SLOT_NAMES,
    WEAPONS,
    ArmourSpec,
    WeaponSpec,
    upgrade_cost,
)
from hollow.domain.calendar import GameCalendar
from hollow.domain.events import (
    ArmourBought,
    ArmourEquipped,
    ArmourRemoved,
    Slot,
    WeaponBought,
    WeaponEquipped,
    WeaponUpgraded,
)
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

    @staticmethod
    def armour_spec(armour_id: str) -> ArmourSpec:
        try:
            return ARMOUR[armour_id]
        except KeyError:
            raise BlacksmithError(f"The blacksmith has never heard of {armour_id}.") from None

    def buy_armour(self, armour_id: str) -> WorldState:
        spec, state = self.armour_spec(armour_id), self.state()
        if state.armory.owns_armour(armour_id):
            raise BlacksmithError(f"You already own the {spec.name}.")
        if not spec.price:
            raise BlacksmithError(f"The {spec.name} is not for sale.")
        if state.souls < spec.price:
            raise BlacksmithError(f"You need {spec.price - state.souls:,} more souls.")
        self._store.append(
            ArmourBought(next_moment(self._store, self._clock), armour_id, spec.price)
        )
        return self.state()

    def wear(self, armour_id: str) -> WorldState:
        spec, state = self.armour_spec(armour_id), self.state()
        if not state.armory.owns_armour(armour_id):
            raise BlacksmithError(f"You do not own the {spec.name}.")
        if state.armory.worn.get(spec.slot) == armour_id:
            raise BlacksmithError(f"You are already wearing the {spec.name}.")
        self._store.append(ArmourEquipped(next_moment(self._store, self._clock), armour_id))
        return self.state()

    def take_off(self, slot: Slot) -> WorldState:
        if slot not in self.state().armory.worn:
            raise BlacksmithError(f"Nothing is worn on your {SLOT_NAMES[slot].lower()}.")
        self._store.append(ArmourRemoved(next_moment(self._store, self._clock), slot))
        return self.state()
