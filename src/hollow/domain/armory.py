"""Weapons, titanite and the blacksmith.

From the plan:
- Each job has its own weapon line. A Ronin weapon only deals damage in Japanese fights,
  an Architect weapon only in dev fights. You start with a plain one of each.
- The blacksmith sells better basic weapons. Bosses drop their own, with a skill.
- Upgrading costs souls and titanite: Shards for +1 to +3, Large Shards for +4 to +6,
  Chunks for +7 to +9, a Slab for +10.
- Bosses scale by region, never by your weapon: above a boss's recommended level each
  extra level adds half the damage, and every boss still needs 60% of its base hits.
- Titanite drops from lessons (rolled when a run ends, see MaterialDropped), bosses,
  merged pull requests (a Chunk each, a Slab for the very first) and every 100 new cards.
"""

import math
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from hollow.domain.activities import ActivityKind, Track
from hollow.domain.events import (
    Event,
    Material,
    MaterialDropped,
    StudyLogged,
    WeaponBought,
    WeaponEquipped,
    WeaponUpgraded,
)


class LessonOutcomeLike(Protocol):
    @property
    def event_id(self) -> UUID: ...
    @property
    def at(self) -> datetime: ...
    @property
    def correct(self) -> int: ...
    @property
    def total(self) -> int: ...
    @property
    def run(self) -> str: ...


BASE_DAMAGE = 10
"""A plain +0 weapon; boss HP is tuned to it."""
FLOOR = 0.6
"""Every boss needs at least this share of its base hits, whatever the weapon."""
MAX_DAMAGE = math.floor(BASE_DAMAGE / FLOOR)
UPGRADE_SOULS = 200
NEW_CARDS_PER_CHUNK = 100


class Skill(StrEnum):
    SOUL_SIPHON = "soul_siphon"


SKILLS = {Skill.SOUL_SIPHON: "Soul Siphon: +15% souls from lessons on its road while equipped"}
SIPHON_PERCENT = 15


@dataclass(frozen=True)
class WeaponSpec:
    id: str
    name: str
    track: Track
    base: int
    per_level: int
    sprite: str
    blurb: str
    price: int = 0
    """Souls at the blacksmith; 0 for starters and boss drops."""
    skill: Skill | None = None
    starter: bool = False
    max_level: int = 10

    def damage(self, level: int, recommended: int) -> int:
        """Damage per correct answer against a boss that expects `recommended`."""
        on_pace = min(level, recommended) * self.per_level
        ahead = max(0, level - recommended) * self.per_level / 2
        return min(MAX_DAMAGE, math.floor(self.base + on_pace + ahead))


WEAPONS: dict[str, WeaponSpec] = {
    w.id: w
    for w in (
        WeaponSpec("rusted-katana", "Rusted Katana", Track.RONIN, 10, 1, "item_katana.png",
                   "Every Ronin starts with one.", starter=True),
        WeaponSpec("uchigatana", "Uchigatana", Track.RONIN, 11, 1, "item_katana.png",
                   "A keen, honest blade.", price=1500),
        WeaponSpec("warden-maul", "Warden's Maul", Track.RONIN, 10, 1, "item_hammer.png",
                   "Pried from the て-form Warden. It still hums with stolen souls.",
                   skill=Skill.SOUL_SIPHON),
        WeaponSpec("worn-hammer", "Worn Hammer", Track.ARCHITECT, 10, 1, "item_hammer.png",
                   "Every Architect starts with one.", starter=True),
        WeaponSpec("smiths-hammer", "Smith's Hammer", Track.ARCHITECT, 11, 1, "item_hammer.png",
                   "Balanced for long days at the forge.", price=1500),
        WeaponSpec("golem-fist", "Golem's Iron Fist", Track.ARCHITECT, 10, 1, "item_hammer.png",
                   "Torn from the Strict Golem. Every joint still checks its types.",
                   skill=Skill.SOUL_SIPHON),
    )
}  # fmt: skip
BOSS_WEAPONS = {"te-warden": "warden-maul", "forge-boss": "golem-fist"}
BOSS_MATERIALS = {
    "te-warden": ((Material.LARGE_SHARD, 3), (Material.CHUNK, 1)),
    "forge-boss": ((Material.LARGE_SHARD, 3), (Material.CHUNK, 1)),
}

MATERIAL_NAMES = {
    Material.SHARD: "Titanite Shard",
    Material.LARGE_SHARD: "Large Titanite Shard",
    Material.CHUNK: "Titanite Chunk",
    Material.SLAB: "Titanite Slab",
}


def upgrade_cost(to_level: int) -> tuple[int, Material, int]:
    """Souls, material and count to reach `to_level`."""
    if to_level >= 10:
        return UPGRADE_SOULS * to_level, Material.SLAB, 1
    tier = (to_level - 1) // 3
    material = (Material.SHARD, Material.LARGE_SHARD, Material.CHUNK)[tier]
    return UPGRADE_SOULS * to_level, material, (to_level - 1) % 3 + 1


@dataclass(frozen=True)
class Drop:
    at: datetime
    material: Material
    count: int
    source: str


@dataclass
class Armory:
    levels: dict[str, int] = field(default_factory=dict)
    """Owned weapons and their upgrade levels."""
    equipped: dict[Track, str] = field(default_factory=dict)
    materials: dict[Material, int] = field(default_factory=lambda: dict.fromkeys(Material, 0))
    drops: list[Drop] = field(default_factory=list)
    equips: list[tuple[datetime, str]] = field(default_factory=list)

    def owns(self, weapon_id: str) -> bool:
        return weapon_id in self.levels

    def weapon(self, track: Track) -> tuple[WeaponSpec, int]:
        weapon_id = self.equipped[track]
        return WEAPONS[weapon_id], self.levels[weapon_id]

    def equipped_at(self, track: Track, moment: datetime) -> str:
        current = next(w.id for w in WEAPONS.values() if w.track is track and w.starter)
        for at, weapon_id in self.equips:
            if at > moment:
                break
            if WEAPONS[weapon_id].track is track:
                current = weapon_id
        return current


def build(events: Iterable[Event], defeated: dict[str, datetime]) -> Armory:
    """Replays the armory. `defeated` maps each felled boss to when it first fell."""
    armory = Armory()
    for w in WEAPONS.values():
        if w.starter:
            armory.levels[w.id] = 0
            armory.equipped[w.track] = w.id
    for boss_id, at in defeated.items():
        if boss_id in BOSS_WEAPONS:
            armory.levels.setdefault(BOSS_WEAPONS[boss_id], 0)
        for material, count in BOSS_MATERIALS.get(boss_id, ()):
            armory.drops.append(Drop(at, material, count, f"boss:{boss_id}"))

    prs = new_cards = 0
    for event in sorted(events, key=lambda e: e.occurred_at):
        if isinstance(event, StudyLogged):
            if event.kind is ActivityKind.PULL_REQUEST:
                for _ in range(event.quantity):
                    prs += 1
                    material = Material.SLAB if prs == 1 else Material.CHUNK
                    armory.drops.append(Drop(event.occurred_at, material, 1, "pull-request"))
            elif event.kind is ActivityKind.ANKI_NEW_CARDS:
                before = new_cards // NEW_CARDS_PER_CHUNK
                new_cards += event.quantity
                for n in range(before, new_cards // NEW_CARDS_PER_CHUNK):
                    source = f"milestone:{(n + 1) * NEW_CARDS_PER_CHUNK}-new-cards"
                    armory.drops.append(Drop(event.occurred_at, Material.CHUNK, 1, source))
        elif isinstance(event, MaterialDropped):
            armory.drops.append(Drop(event.occurred_at, event.material, event.count, event.source))
        elif isinstance(event, WeaponBought) and event.weapon_id in WEAPONS:
            armory.levels.setdefault(event.weapon_id, 0)
        elif isinstance(event, WeaponUpgraded) and armory.owns(event.weapon_id):
            armory.levels[event.weapon_id] = max(armory.levels[event.weapon_id], event.level)
            armory.materials[event.material] -= event.material_count
        elif isinstance(event, WeaponEquipped) and armory.owns(event.weapon_id):
            armory.equipped[WEAPONS[event.weapon_id].track] = event.weapon_id
            armory.equips.append((event.occurred_at, event.weapon_id))
    for drop in armory.drops:
        armory.materials[drop.material] += drop.count
    armory.drops.sort(key=lambda d: d.at)
    return armory


GOOD = 0.9
DRY_LIMIT = 4
"""After this many good lessons in a row without a drop, the next good one drops for sure."""
DROP_CHANCE = {  # (refresher due?, perfect?) -> chance
    (True, True): 1.0,
    (True, False): 0.6,
    (False, True): 0.5,
    (False, False): 0.25,
}
LARGE_FROM_STEP = 2
"""Refreshers from the 7-day interval on drop Large Shards: long gaps, better loot."""


def lesson_drop(
    refresher: bool, practice: bool, correct: int, total: int, step: int, dry: int, roll: float
) -> Material | None:
    """What a finished lesson drops. `step` is the refresher interval before this run,
    `dry` the good runs since the last lesson drop, `roll` a random number in [0, 1)."""
    if practice or correct < GOOD * total:
        return None
    chance = 1.0 if dry >= DRY_LIMIT else DROP_CHANCE[(refresher, correct == total)]
    if roll >= chance:
        return None
    return Material.LARGE_SHARD if refresher and step >= LARGE_FROM_STEP else Material.SHARD


def dry_streak(outcomes: Iterable["LessonOutcomeLike"], dropped: set[str]) -> int:
    """Good, non-practice lesson runs since the last one that dropped titanite."""
    dry = 0
    for o in sorted(outcomes, key=lambda o: o.at):
        if o.correct < GOOD * o.total or o.run == "practice":
            continue
        dry = 0 if f"lesson:{o.event_id}" in dropped else dry + 1
    return dry
