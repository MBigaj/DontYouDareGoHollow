"""The world maps: regions on the world map, and the points inside a region.

Coordinates are in map pixels (the art's native pixel grid), so the art script and the
pages place things in the same spots. Pages turn them into percentages.
"""

from dataclasses import dataclass
from enum import StrEnum

WORLD_SIZE = (260, 225)
"""Grid of the world map art (map_bg.png is 4 px per unit, drawn at 2x density)."""
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
    area: tuple[tuple[int, int], ...] = ()
    """The landmark's outline on the world map: hovering it lights it, clicking it walks there."""


REGIONS: tuple[Region, ...] = (
    Region(
        "firelink", 1, "Firelink Shrine", "始まりの火", "はじまりのひ",
        "Where every journey starts: the first 250 core words and the grammar that holds "
        "simple sentences together.",
        "Core 2000 cards 1-250", "Polite forms, particles, て-form", "The て-form Warden",
        (21, 185), open=True,
        area=((2, 195), (2, 172), (10, 160), (27, 158), (30, 168), (42, 170), (44, 195)),
    ),
    Region(
        "undead-village", 2, "Undead Village", "静かな村", "しずかなむら",
        "Quiet streets where things are always happening. Describe what is going on and what "
        "already happened.",
        "Cards 251-500", "〜ている, 〜た, plain form", "The Plain-Form Gargoyle", (70, 152),
        area=((36, 165), (38, 150), (46, 146), (58, 140), (78, 139), (80, 128), (85, 128),
              (87, 138), (98, 140), (102, 150), (100, 165)),
    ),
    Region(
        "kanji-catacombs", 3, "Kanji Catacombs", "漢字の地下", "かんじのちか",
        "Old stones carved with characters. Readings matter here more than anywhere.",
        "Cards 501-800", "〜たい, 〜ない, comparisons", "The Bone Scribe", (40, 97),
        area=((18, 112), (20, 80), (30, 70), (48, 70), (58, 78), (60, 112)),
    ),
    Region(
        "sens-fortress", 4, "Sen's Fortress", "出来る力", "できるちから",
        "Traps everywhere. Say what you can and cannot do, and what you think.",
        "Cards 801-1100", "Potential form, 〜と思う", "The Iron Golem of Ability", (149, 79),
        area=((116, 100), (118, 76), (122, 72), (128, 74), (142, 68), (150, 62), (160, 61),
              (166, 70), (174, 74), (176, 100)),
    ),
    Region(
        "anor-keigo", 5, "Anor Keigo", "もし", "もし",
        "A golden city of conditions. Nothing here happens unless something else does first.",
        "Cards 1101-1500", "ば, たら, と, なら", "Ornstein and Smough of If", (209, 48),
        area=((188, 70), (190, 48), (200, 40), (208, 28), (212, 26), (216, 38), (228, 42),
              (238, 50), (240, 70)),
    ),
    Region(
        "the-kiln", 6, "The Kiln", "最後の火", "さいごのひ",
        "The first flame burns at the top of the world. Clearing it lines up with JLPT N4.",
        "Cards 1501-2000", "Passive, causative, intro to keigo", "Lord of Conjugation",
        (242, 24),
        area=((222, 45), (232, 24), (238, 5), (244, 0), (250, 0), (254, 20), (260, 30), (260, 45)),
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
    area: tuple[tuple[int, int], ...] = ()
    """A landmark's outline, for places that are a painted building rather than a stone."""


FIRELINK: tuple[Node, ...] = (
    Node(
        "bonfire",
        NodeKind.BONFIRE,
        (32, 124),
        area=((12, 136), (14, 122), (22, 112), (30, 104), (36, 112), (44, 124), (46, 136)),
    ),
    Node("te-ru", NodeKind.LESSON, (64, 112), "te-ru"),
    Node("te-tsu", NodeKind.LESSON, (98, 122), "te-tsu"),
    Node("te-nde", NodeKind.LESSON, (130, 106), "te-nde"),
    Node("te-ite", NodeKind.LESSON, (104, 86), "te-ite"),
    Node("te-shite", NodeKind.LESSON, (138, 72), "te-shite"),
    Node("te-irregular", NodeKind.LESSON, (174, 84), "te-irregular"),
    Node("te-mixed", NodeKind.LESSON, (196, 62), "te-mixed"),
    Node(
        "warden",
        NodeKind.BOSS,
        (226, 42),
        area=(
            (198, 52),
            (200, 12),
            (205, 3),
            (212, 3),
            (216, 14),
            (222, 22),
            (232, 20),
            (240, 28),
            (244, 52),
        ),
    ),
)
"""The path through Firelink Shrine, in walking order."""

VILLAGE_SIZE = (260, 150)
"""Grid of the Undead Village art (region_undead_village.png is 4 px per unit, 2x density)."""

VILLAGE: tuple[Node, ...] = (
    Node("bonfire", NodeKind.BONFIRE, (27, 128),
         area=((15, 138), (17, 126), (24, 120), (29, 116), (33, 122), (37, 130), (38, 138))),
    Node("pf-teiru", NodeKind.LESSON, (63, 120), "pf-teiru"),
    Node("pf-ta", NodeKind.LESSON, (101, 106), "pf-ta"),
    Node("pf-nai-ru", NodeKind.LESSON, (141, 97), "pf-nai-ru"),
    Node("pf-nai-u", NodeKind.LESSON, (168, 79), "pf-nai-u"),
    Node("pf-nakatta", NodeKind.LESSON, (200, 65), "pf-nakatta"),
    Node("pf-mixed", NodeKind.LESSON, (221, 50), "pf-mixed"),
    Node("gargoyle", NodeKind.BOSS, (234, 30),
         area=((205, 40), (206, 17), (214, 11), (222, 12), (228, 0), (240, 0), (248, 10),
               (258, 14), (260, 40))),
)  # fmt: skip
"""The street up through Undead Village, in walking order: the well, the bridge, the stairs,
and the gargoyle's gatehouse at the top."""

RONIN_REGION_MAPS: dict[str, tuple[tuple[Node, ...], tuple[int, int], str]] = {
    "firelink": (FIRELINK, FIRELINK_SIZE, "region_firelink.png"),
    "undead-village": (VILLAGE, VILLAGE_SIZE, "region_undead_village.png"),
}
"""Ronin region maps drawn so far: nodes, art size and art file."""


# --- the Architect road ---------------------------------------------------------

ARCH_WORLD_SIZE = (260, 225)
"""Grid of the Architect world art (map_architect.png is 4 px per unit, drawn at 2x density)."""
FORGE_SIZE = (260, 150)
"""Grid of the Forge art (region_forge.png is 4 px per unit, drawn at 2x density)."""
DEPTHS_SIZE = (260, 150)
"""Grid of the Data Depths art (region_data_depths.png is 4 px per unit, drawn at 2x density)."""

ARCH_POINTS: dict[str, tuple[int, int]] = {
    "forge": (29, 176),
    "data-depths": (92, 160),
    "api-citadel": (171, 171),
    "async-ruins": (240, 136),
    "watchtower": (236, 79),
    "iron-keep": (132, 75),
    "undercroft": (37, 83),
    "distributed-abyss": (134, 26),
}
"""Where each Architect region sits on its world map, in road order."""

ARCH_AREAS: dict[str, tuple[tuple[int, int], ...]] = {
    "forge": ((2, 193), (2, 154), (15, 152), (14, 136), (22, 135), (23, 152), (53, 154),
              (54, 193)),
    "data-depths": ((48, 189), (49, 152), (59, 141), (83, 134), (110, 135), (136, 143),
                    (140, 158), (127, 189)),
    "api-citadel": ((134, 191), (134, 158), (149, 152), (158, 141), (171, 143), (189, 138),
                    (193, 152), (204, 158), (205, 191)),
    "async-ruins": ((217, 154), (218, 131), (225, 126), (233, 128), (240, 121), (248, 121),
                    (250, 99), (256, 96), (260, 99), (260, 154)),
    "watchtower": ((222, 92), (226, 73), (229, 55), (233, 44), (239, 44), (243, 55), (246, 73),
                   (248, 92)),
    "iron-keep": ((105, 90), (108, 62), (119, 55), (130, 35), (139, 37), (143, 57), (158, 66),
                  (159, 90)),
    "undercroft": ((9, 99), (11, 66), (20, 51), (33, 42), (51, 42), (62, 53), (66, 72), (66, 99)),
    "distributed-abyss": ((79, 48), (84, 18), (110, 2), (149, 0), (189, 4), (207, 26),
                          (204, 51)),
}  # fmt: skip
"""Each Architect region's landmark on its world map: the smithy, the flooded vault, the
citadel, the ruined towers, the watchtower, the iron keep, the crypt stair and the abyss."""

FORGE: tuple[Node, ...] = (
    Node("bonfire", NodeKind.BONFIRE, (24, 126),
         area=((7, 137), (9, 128), (16, 122), (23, 108), (29, 122), (37, 126), (38, 137))),
    Node("mypy-strict-in-practice", NodeKind.LESSON, (52, 125), "mypy-strict-in-practice"),
    Node("asyncio-internals", NodeKind.LESSON, (87, 113), "asyncio-internals"),
    Node("concurrency-choices-threads-processes-async", NodeKind.LESSON, (129, 122),
         "concurrency-choices-threads-processes-async"),
    Node("profiling-and-performance", NodeKind.LESSON, (104, 97), "profiling-and-performance"),
    Node("property-based-testing", NodeKind.LESSON, (146, 101), "property-based-testing"),
    Node("test-architecture", NodeKind.LESSON, (170, 94), "test-architecture"),
    Node("packaging-and-tooling-with-uv", NodeKind.LESSON, (188, 83),
         "packaging-and-tooling-with-uv"),
    Node("python-memory-model", NodeKind.LESSON, (209, 73), "python-memory-model"),
    Node("forge-boss", NodeKind.BOSS, (226, 64),
         area=((184, 69), (186, 10), (196, 5), (214, 7), (228, 16), (242, 7), (252, 10),
               (257, 69))),
)  # fmt: skip
"""The path through the Forge, in walking order; lesson nodes carry the step id."""

DEPTHS: tuple[Node, ...] = (
    Node("bonfire", NodeKind.BONFIRE, (28, 126),
         area=((13, 134), (15, 121), (26, 113), (32, 121), (36, 134))),
    Node("mvcc-and-isolation-levels", NodeKind.LESSON, (54, 118), "mvcc-and-isolation-levels"),
    Node("locks-deadlocks-and-contention", NodeKind.LESSON, (78, 108),
         "locks-deadlocks-and-contention"),
    Node("reading-query-plans", NodeKind.LESSON, (101, 105), "reading-query-plans"),
    Node("index-design", NodeKind.LESSON, (122, 102), "index-design"),
    Node("zero-downtime-migrations", NodeKind.LESSON, (144, 98), "zero-downtime-migrations"),
    Node("replication-and-read-replicas", NodeKind.LESSON, (146, 83),
         "replication-and-read-replicas"),
    Node("partitioning-and-sharding", NodeKind.LESSON, (163, 78), "partitioning-and-sharding"),
    Node("caching-patterns-and-invalidation", NodeKind.LESSON, (184, 76),
         "caching-patterns-and-invalidation"),
    Node("redis-beyond-caching", NodeKind.LESSON, (200, 73), "redis-beyond-caching"),
    Node("postgresql-vs-mongodb-modelling", NodeKind.LESSON, (189, 63),
         "postgresql-vs-mongodb-modelling"),
    Node("connection-pooling-under-load", NodeKind.LESSON, (205, 57),
         "connection-pooling-under-load"),
    Node("data-depths-boss", NodeKind.BOSS, (228, 50),
         area=((205, 52), (207, 17), (215, 5), (234, 0), (253, 3), (260, 10), (260, 52))),
)  # fmt: skip
"""The walkways through the flooded vault of Data Depths, in walking order."""

ARCH_REGION_MAPS: dict[str, tuple[tuple[Node, ...], tuple[int, int], str]] = {
    "forge": (FORGE, FORGE_SIZE, "region_forge.png"),
    "data-depths": (DEPTHS, DEPTHS_SIZE, "region_data_depths.png"),
}
"""Region maps drawn so far: nodes, art size and art file."""
