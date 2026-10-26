"""The world maps: regions on the world map, and the points inside a region.

Coordinates are in map pixels (the art's native pixel grid), so the art script and the
pages place things in the same spots. Pages turn them into percentages.
"""

from dataclasses import dataclass
from enum import StrEnum

WORLD_SIZE = (260, 225)
"""Native size of the world map art (map_bg.png, drawn at 4x)."""
FIRELINK_SIZE = (260, 150)
"""Native size of the Firelink Shrine art (region_firelink.png, drawn at 4x)."""


@dataclass(frozen=True)
class Region:
    id: str
    number: int
    name: str
    jp: str
    jp_kana: str
    blurb: str
    cards: str
    topics: str
    boss: str
    point: tuple[int, int]
    open: bool = False


REGIONS: tuple[Region, ...] = (
    Region(
        "firelink", 1, "Firelink Shrine", "始まりの火", "はじまりのひ",
        "Where every journey starts: the first 250 core words and the grammar that holds "
        "simple sentences together.",
        "Core 2000 cards 1-250", "Polite forms, particles, て-form", "The て-form Warden",
        (52, 175), open=True,
    ),
    Region(
        "undead-village", 2, "Undead Village", "静かな村", "しずかなむら",
        "Quiet streets where things are always happening. Describe what is going on and what "
        "already happened.",
        "Cards 251-500", "〜ている, 〜た, plain form", "The Plain-Form Gargoyle", (97, 152),
    ),
    Region(
        "kanji-catacombs", 3, "Kanji Catacombs", "漢字の地下", "かんじのちか",
        "Old stones carved with characters. Readings matter here more than anywhere.",
        "Cards 501-800", "〜たい, 〜ない, comparisons", "The Bone Scribe", (75, 117),
    ),
    Region(
        "sens-fortress", 4, "Sen's Fortress", "出来る力", "できるちから",
        "Traps everywhere. Say what you can and cannot do, and what you think.",
        "Cards 801-1100", "Potential form, 〜と思う", "The Iron Golem of Ability", (140, 120),
    ),
    Region(
        "anor-keigo", 5, "Anor Keigo", "もし", "もし",
        "A golden city of conditions. Nothing here happens unless something else does first.",
        "Cards 1101-1500", "ば, たら, と, なら", "Ornstein and Smough of If", (190, 80),
    ),
    Region(
        "the-kiln", 6, "The Kiln", "最後の火", "さいごのひ",
        "The first flame burns at the top of the world. Clearing it lines up with JLPT N4.",
        "Cards 1501-2000", "Passive, causative, intro to keigo", "Lord of Conjugation",
        (225, 37),
    ),
)  # fmt: skip


class NodeKind(StrEnum):
    BONFIRE = "bonfire"
    LESSON = "lesson"
    BOSS = "boss"


@dataclass(frozen=True)
class Node:
    id: str
    kind: NodeKind
    point: tuple[int, int]
    lesson_id: str | None = None


FIRELINK: tuple[Node, ...] = (
    Node("bonfire", NodeKind.BONFIRE, (32, 124)),
    Node("te-ru", NodeKind.LESSON, (64, 112), "te-ru"),
    Node("te-tsu", NodeKind.LESSON, (98, 122), "te-tsu"),
    Node("te-nde", NodeKind.LESSON, (130, 106), "te-nde"),
    Node("te-ite", NodeKind.LESSON, (104, 86), "te-ite"),
    Node("te-shite", NodeKind.LESSON, (138, 72), "te-shite"),
    Node("te-irregular", NodeKind.LESSON, (174, 84), "te-irregular"),
    Node("te-mixed", NodeKind.LESSON, (196, 62), "te-mixed"),
    Node("warden", NodeKind.BOSS, (226, 42)),
)
"""The path through Firelink Shrine, in walking order."""


# --- the Architect road ---------------------------------------------------------

ARCH_WORLD_SIZE = (260, 225)
"""Native size of the Architect world art (map_architect.png, drawn at 4x)."""
FORGE_SIZE = (260, 150)
"""Native size of the Forge region art (region_forge.png, drawn at 4x)."""
DEPTHS_SIZE = (260, 150)
"""Native size of the Data Depths art (region_data_depths.png, drawn at 4x)."""

ARCH_POINTS: dict[str, tuple[int, int]] = {
    "forge": (38, 192),
    "data-depths": (98, 182),
    "api-citadel": (160, 176),
    "async-ruins": (220, 156),
    "watchtower": (214, 100),
    "iron-keep": (152, 110),
    "undercroft": (82, 116),
    "distributed-abyss": (130, 50),
}
"""Where each Architect region sits on its world map, in road order."""

FORGE: tuple[Node, ...] = (
    Node("bonfire", NodeKind.BONFIRE, (26, 120)),
    Node("mypy-strict-in-practice", NodeKind.LESSON, (58, 106), "mypy-strict-in-practice"),
    Node("asyncio-internals", NodeKind.LESSON, (88, 122), "asyncio-internals"),
    Node("concurrency-choices-threads-processes-async", NodeKind.LESSON, (118, 104),
         "concurrency-choices-threads-processes-async"),
    Node("profiling-and-performance", NodeKind.LESSON, (94, 80), "profiling-and-performance"),
    Node("property-based-testing", NodeKind.LESSON, (126, 64), "property-based-testing"),
    Node("test-architecture", NodeKind.LESSON, (158, 82), "test-architecture"),
    Node("packaging-and-tooling-with-uv", NodeKind.LESSON, (188, 100),
         "packaging-and-tooling-with-uv"),
    Node("python-memory-model", NodeKind.LESSON, (204, 70), "python-memory-model"),
    Node("forge-boss", NodeKind.BOSS, (230, 40)),
)  # fmt: skip
"""The path through the Forge, in walking order; lesson nodes carry the step id."""

DEPTHS: tuple[Node, ...] = (
    Node("bonfire", NodeKind.BONFIRE, (22, 124)),
    Node("mvcc-and-isolation-levels", NodeKind.LESSON, (48, 108), "mvcc-and-isolation-levels"),
    Node("locks-deadlocks-and-contention", NodeKind.LESSON, (76, 124),
         "locks-deadlocks-and-contention"),
    Node("reading-query-plans", NodeKind.LESSON, (104, 110), "reading-query-plans"),
    Node("index-design", NodeKind.LESSON, (90, 86), "index-design"),
    Node("zero-downtime-migrations", NodeKind.LESSON, (118, 70), "zero-downtime-migrations"),
    Node("replication-and-read-replicas", NodeKind.LESSON, (148, 84),
         "replication-and-read-replicas"),
    Node("partitioning-and-sharding", NodeKind.LESSON, (176, 102), "partitioning-and-sharding"),
    Node("caching-patterns-and-invalidation", NodeKind.LESSON, (204, 118),
         "caching-patterns-and-invalidation"),
    Node("redis-beyond-caching", NodeKind.LESSON, (228, 94), "redis-beyond-caching"),
    Node("postgresql-vs-mongodb-modelling", NodeKind.LESSON, (198, 72),
         "postgresql-vs-mongodb-modelling"),
    Node("connection-pooling-under-load", NodeKind.LESSON, (168, 54),
         "connection-pooling-under-load"),
    Node("data-depths-boss", NodeKind.BOSS, (226, 38)),
)  # fmt: skip
"""The walkways through the flooded vault of Data Depths, in walking order."""

ARCH_REGION_MAPS: dict[str, tuple[tuple[Node, ...], tuple[int, int], str]] = {
    "forge": (FORGE, FORGE_SIZE, "region_forge.png"),
    "data-depths": (DEPTHS, DEPTHS_SIZE, "region_data_depths.png"),
}
"""Region maps drawn so far: nodes, art size and art file."""
