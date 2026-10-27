"""Ronin map waypoints: rune stones carved with て, 24x28 drawn at 2x (48x56 files).

Small enough that drawing them in code beats generating them; ronin.py saves them.
"""

import numpy as np
from PIL import Image

from kit import ASH, Canvas, blend, hx, ramp


def waypoint(glyph: np.ndarray, body: list[np.ndarray], lit: bool) -> Canvas:
    c = Canvas(24, 28)
    stone = c.poly([(5, 25), (4, 9), (7, 3), (11, 1), (15, 2), (19, 8), (19, 25)])
    c.shade(stone, body, light=(-0.8, -0.6), soft=1.4, lo=0.12, hi=0.95, relief=3)
    c.fill(c.line([(8, 6), (7, 22)]), body[min(len(body) - 1, 4)])
    rune = (c.line([(9, 9), (15, 9)]) | c.line([(13, 9), (11, 13)]) | c.line([(11, 13), (11, 18)])
            | c.line([(11, 18), (15, 20)]))  # fmt: skip
    if lit:  # a faint glow around the carving
        halo = np.zeros_like(rune)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            halo |= np.roll(np.roll(rune, dx, 1), dy, 0)
        c.fill(halo & stone & ~rune, blend(body[2], glyph, 0.45))
    c.fill(rune, glyph)
    c.fill(c.rect((2, 24, 21, 27)), body[1])
    c.fill(c.rect((3, 24, 20, 24)), body[3])
    c.outline(darken=0.25)
    return c


def waypoints() -> dict[str, Image.Image]:
    gold = ramp("2e2416", "4a3a22", "6e5634", "9a7c48", "c8a466")
    stones = {
        "waypoint.png": waypoint(hx("f6c55a"), ASH, True),
        "waypoint_cleared.png": waypoint(hx("fff0c0"), gold, True),
        "waypoint_locked.png": waypoint(ASH[1], ASH, False),
    }
    return {name: c.img().resize((48, 56), Image.NEAREST) for name, c in stones.items()}
