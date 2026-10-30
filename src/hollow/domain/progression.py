"""Stats bought with souls, and job levels earned from lifetime souls.

- Stats are bought at the bonfire with unspent souls. Every level bought raises your soul
  level, and the next level costs more: 200 + 40 x soul level.
- Vigor and Endurance make boss fights more forgiving. Faith and Intelligence unlock extras
  for the Ronin and the Architect. No stat ever locks study content.
- Jobs level from the souls you earned in their track, which are never lost or spent.
"""

from dataclasses import dataclass
from enum import StrEnum

from hollow.domain.activities import Track

BASE_COST = 200
COST_PER_LEVEL = 40
STAT_START = 1
STAT_MAX = 99

BASE_HP = 100
HP_PER_VIGOR = 10
BASE_MISTAKE_COST = 35
MIN_MISTAKE_COST = 20


class Stat(StrEnum):
    VIGOR = "vigor"
    ENDURANCE = "endurance"
    FAITH = "faith"
    INTELLIGENCE = "intelligence"


@dataclass(frozen=True)
class Perk:
    level: int
    text: str


@dataclass(frozen=True)
class StatSpec:
    stat: Stat
    label: str
    track: Track | None
    blurb: str
    perks: tuple[Perk, ...] = ()


STATS: dict[Stat, StatSpec] = {
    s.stat: s
    for s in (
        StatSpec(Stat.VIGOR, "Vigor", None, "+10 max HP in boss fights"),
        StatSpec(Stat.ENDURANCE, "Endurance", None, "Mistakes in boss fights cost 1 HP less"),
        StatSpec(
            Stat.FAITH,
            "Faith",
            Track.RONIN,
            "Unlocks extras for the Ronin",
            (
                Perk(3, "Furigana lens: one free each week"),
                Perk(5, "Sensei: everyday conversation topics"),
                Perk(10, "Sensei: travel and food topics"),
                Perk(15, "Phantom sign: one free Sensei hint per boss"),
            ),
        ),
        StatSpec(
            Stat.INTELLIGENCE,
            "Intelligence",
            Track.ARCHITECT,
            "Unlocks extras for the Architect",
            (
                Perk(3, "Tech Lead: a hint on any topic exam"),
                Perk(5, "Echo challenges: one extra each week"),
                Perk(10, "Ring slot: wear a second ring"),
                Perk(15, "Phantom sign: one free Tech Lead hint per boss"),
            ),
        ),
    )
}


def level_cost(soul_level: int) -> int:
    """Souls needed for the next stat level."""
    return BASE_COST + COST_PER_LEVEL * soul_level


def max_hp(vigor: int) -> int:
    return BASE_HP + HP_PER_VIGOR * (vigor - STAT_START)


def mistake_cost(endurance: int, reduction: int = 0) -> int:
    """HP a wrong answer costs in a boss fight; `reduction` comes from armour."""
    return max(MIN_MISTAKE_COST, BASE_MISTAKE_COST - (endurance - STAT_START) - reduction)


@dataclass(frozen=True)
class JobProgress:
    track: Track
    level: int
    xp: int
    into_level: int
    """XP gained since reaching the current level."""
    needed: int
    """XP the current level takes to finish."""

    @property
    def percent(self) -> int:
        return min(100, self.into_level * 100 // self.needed)


def xp_for_next(level: int) -> int:
    """Going from `level` to `level + 1` takes 100 x level XP: 100, 200, 300…"""
    return 100 * level


def job_progress(track: Track, xp: int) -> JobProgress:
    level, floor = 1, 0
    while xp >= floor + xp_for_next(level):
        floor += xp_for_next(level)
        level += 1
    return JobProgress(track, level, xp, xp - floor, xp_for_next(level))
