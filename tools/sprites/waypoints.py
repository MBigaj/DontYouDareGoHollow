"""Ronin map waypoints: grave stones with a carved kana, 24x28 drawn at 2x (48x56 files).

The stone comes from a generated painting (art/source/tombstone.jpg, prompt in PROMPTS.md):
its light, cracks and moss are averaged onto the grid and painted in ASH, then the parts too
small for the pipeline are drawn here: the slab's outline, the warm rim light, the recessed
panel, the kana (て for Firelink, た for Undead Village) and the dry grass at its foot.
ronin.py saves them.
"""

import numpy as np
from PIL import Image

from generated import SRC
from kit import ASH, MOSS, Canvas, blend, hx, ramp

W, H = 24, 28
SLAB = [(4, 21), (4, 4), (5, 2), (7, 1), (16, 1), (18, 2), (19, 4), (19, 21)]
PLINTH = (2, 21, 21, 25)
PANEL = (7, 5, 16, 18)
"""The panel's flat inside, where the kana is carved."""
SOURCE_SLAB = (310, 22, 692, 720)
"""The slab's left, top, right and bottom edges on tombstone.jpg (1024x1024)."""

GLYPHS = {
    "te": ["#######",
           "....##.",
           "...#...",
           "...#...",
           "...#...",
           "...#...",
           "....#..",
           ".....##"],
    "ta": ["..#.....",
           "#####...",
           "..#.....",
           ".#..###.",
           ".#......",
           ".#.#....",
           "#..#....",
           "#...###."],
}  # fmt: skip
"""Each region's kana, one pixel per character."""

STRAW = ramp("3a2c14", "6a5224", "9c7c34", "c8a050")
TUFTS = {  # grass blades by shade, darkest first: the plinth's corners and a few in front
    0: [(2, 25), (3, 25), (4, 25), (19, 25), (20, 25), (21, 25), (10, 25), (11, 25)],
    1: [(2, 24), (3, 23), (4, 24), (20, 24), (21, 23), (19, 24), (11, 24), (14, 25), (15, 25)],
    2: [(1, 23), (3, 22), (20, 23), (22, 22), (10, 24), (15, 24), (6, 25), (7, 25)],
    3: [(1, 22), (21, 22), (12, 24), (6, 24)],
}


def painted() -> tuple[np.ndarray, np.ndarray]:
    """The painting's light (0..1) and moss (0..1), averaged onto the grid so its slab lands
    on SLAB."""
    left, top, right, bottom = SOURCE_SLAB
    sx, sy = (right - left) / (SLAB[-1][0] - SLAB[0][0]), (bottom - top) / (SLAB[0][1] - 1)
    x0, y0 = left - SLAB[0][0] * sx, top - sy
    box = (round(x0), round(y0), round(x0 + W * sx), round(y0 + H * sy))
    im = Image.open(SRC / "tombstone.jpg").convert("RGB").crop(box).resize((W, H), Image.BOX)
    a = np.array(im).astype(float)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    light = (a @ np.array([0.3, 0.59, 0.11])) / 255
    moss = np.clip((g - b) / 40 - np.clip((r - g) / 25, 0, None), 0, 1)
    return light, moss


def carved(kana: str) -> np.ndarray:
    rows = GLYPHS[kana]
    m = np.zeros((H, W), bool)
    x0, y0, x1, y1 = PANEL
    ox = x0 + (x1 - x0 + 2 - len(rows[0])) // 2
    oy = y0 + (y1 - y0 + 1 - len(rows)) // 2
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            m[oy + y, ox + x] = ch == "#"
    return m


def waypoint(kana: str, body: list[np.ndarray], rim: np.ndarray, glow: np.ndarray | None) -> Canvas:
    """One stone: lit (glow is the kana's colour) or cold (glow None, the kana cut dark)."""
    light, moss = painted()
    c = Canvas(W, H)
    slab, plinth = c.poly(SLAB), c.rect(PLINTH)
    solid = slab | plinth
    lo, hi = light[solid].min(), light[solid].max()
    val = np.clip((light - lo) / (hi - lo + 1e-6), 0, 1) ** 0.75
    c.levels(solid, val * 0.7 + 0.3, body, dither=0.6)
    c.levels(solid & (moss > 0.35), np.clip(val * 0.9 + 0.1, 0, 1), MOSS[1:], dither=0.4)
    # the right faces fall into shadow, the left edge and the arch catch the warm light
    c.fill(slab & (c.xx >= 18), body[1])
    c.fill(plinth & (c.xx >= 20), body[1])
    edge = (slab & ~np.roll(slab, 1, 1)) | (slab & ~np.roll(slab, 1, 0) & (c.xx < 14))
    c.fill(edge, rim)
    c.fill(plinth & (c.yy == PLINTH[1]) & (c.xx < 18), blend(body[-2], rim, 0.4))
    c.fill(plinth & (c.xx == PLINTH[0]), blend(body[-3], rim, 0.5))
    c.fill(plinth & (c.yy == PLINTH[3]), body[1])
    # the recessed panel: a step darker, shadowed top and left, a lit lip below
    x0, y0, x1, y1 = PANEL
    inner = c.rect(PANEL)
    c.levels(inner, np.clip(val * 0.4 + 0.36, 0, 1), body, dither=0.4)
    c.fill(c.rect((x0 - 1, y0 - 1, x1, y0 - 1)) | c.rect((x0 - 1, y0 - 1, x0 - 1, y1)), body[0])
    c.fill(c.rect((x0, y1 + 1, x1 + 1, y1 + 1)), body[-3])
    c.fill(c.rect((x1 + 1, y0, x1 + 1, y1)), body[2])
    kana_px = carved(kana)
    if glow is None:  # cut into the stone, its lower lip catching the light
        c.fill(kana_px, body[0])
        c.fill(np.roll(np.roll(kana_px, 1, 0), 1, 1) & ~kana_px & inner, body[-3])
    else:  # lit from inside, with a faint halo on the panel
        halo = np.zeros_like(kana_px)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            halo |= np.roll(np.roll(kana_px, dx, 1), dy, 0)
        halo &= inner & ~kana_px
        c.a[halo, :3] = [blend(px, glow, 0.35) for px in c.a[halo, :3]]
        c.fill(kana_px, glow)
    for shade, blades in TUFTS.items():
        for x, y in blades:
            c.dot(x, y, STRAW[shade])
    c.outline(darken=0.25)
    return c


def waypoints() -> dict[str, Image.Image]:
    """Firelink's て stones (waypoint*.png) and Undead Village's た stones (waypoint_ta*.png)."""
    gold = ramp("2e2416", "4a3a22", "6e5634", "9a7c48", "c8a466")
    stones = {}
    for kana, suffix in (("te", ""), ("ta", "_ta")):
        stones[f"waypoint{suffix}.png"] = waypoint(kana, ASH, hx("e6b866"), hx("f6c55a"))
        stones[f"waypoint{suffix}_cleared.png"] = waypoint(kana, gold, hx("f6d98a"), hx("fff0c0"))
        stones[f"waypoint{suffix}_locked.png"] = waypoint(kana, ASH, ASH[-2], None)
    return {name: c.img().resize((W * 2, H * 2), Image.NEAREST) for name, c in stones.items()}
