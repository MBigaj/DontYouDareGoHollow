"""Firelink Shrine region map (placeholder pixel art), plus the map waypoint sprites.

Draws at native size (see hollow.domain.atlas) and scales up 4x with NEAREST, to match
map_bg.png. The path runs through the atlas points, so the art and the pages agree.
Usage: uv run python tools/sprites/region_firelink.py src/hollow/adapters/web/static/sprites
"""

import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw

from hollow.domain.atlas import FIRELINK, FIRELINK_SIZE

OUT = Path(sys.argv[1])
SCALE = 4


def H(c: str, a: int = 255) -> tuple[int, int, int, int]:
    return (int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16), a)


C = {k: H(v) for k, v in dict(
    out="#0b0a08", s1="#14120f", s2="#1c1814", s3="#231d17", s4="#2e261e", s5="#3b3127",
    d1="#1a1612", d2="#2a231b", d3="#3a3025", d4="#5a4e3e", d5="#8c7f69", l1="#c9bfa9",
    l2="#f1e6d0", e1="#7a3510", e2="#c2611f", e3="#e9a15f", e4="#ffe2bf", g1="#8a6a34",
    g2="#c9a86a", g3="#e9c27a", fog="#5a564e", fog2="#8a867c", moss="#2f3324",
).items()}  # fmt: skip


def dither(img: Image.Image, test, col) -> None:  # type: ignore[no-untyped-def]
    px = img.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            if test(x, y):
                px[x, y] = col


def region() -> Image.Image:
    W, Hh = FIRELINK_SIZE
    img = Image.new("RGBA", (W, Hh), C["s1"])
    d = ImageDraw.Draw(img)
    rng = random.Random(7)
    # sky bands with dithered seams
    for y0, y1, col in ((0, 18, C["s1"]), (18, 34, C["s2"]), (34, 56, C["s3"])):
        d.rectangle((0, y0, W, y1), fill=col)
    dither(img, lambda x, y: y in (17, 18, 33, 34) and (x + y) % 2 == 0, C["s2"])
    # dark sun with a dithered corona
    cx, cy = 46, 22
    for x in range(cx - 18, cx + 19):
        for y in range(max(0, cy - 18), cy + 19):
            r = math.hypot(x - cx, y - cy)
            if r <= 9:
                img.putpixel((x, y), C["out"])
            elif r <= 10.2:
                img.putpixel((x, y), C["g2"])
            elif r <= 14 and (x + y) % 2 == 0:
                img.putpixel((x, y), C["g1"])
            elif r <= 17 and x % 2 == 0 and y % 2 == 0:
                img.putpixel((x, y), C["d4"])
    # far cliffs
    far = [(0, 52), (18, 40), (34, 48), (58, 30), (80, 44), (104, 36), (128, 46), (150, 28),
           (170, 38), (196, 20), (214, 30), (236, 18), (260, 26), (260, 150), (0, 150)]  # fmt: skip
    d.polygon(far, fill=C["s4"])
    dither(img, lambda x, y: 40 <= y <= 62 and (x + y) % 2 == 0 and img.getpixel((x, y)) == C["s4"], C["s3"])
    # mid hills
    mid = [(0, 84), (30, 70), (60, 80), (92, 62), (126, 74), (160, 56), (190, 64), (214, 46),
           (240, 54), (260, 48), (260, 150), (0, 150)]  # fmt: skip
    d.polygon(mid, fill=C["s5"])
    dither(img, lambda x, y: y < 92 and x % 2 == 0 and y % 2 == 0 and img.getpixel((x, y)) == C["s5"], C["s4"])
    # foreground ground
    near = [(0, 104), (40, 98), (80, 104), (120, 92), (160, 98), (200, 86), (260, 90),
            (260, 150), (0, 150)]  # fmt: skip
    d.polygon(near, fill=H("#2b241c"))
    dither(img, lambda x, y: 86 <= y <= 110 and x % 2 == 0 and y % 2 == 0 and img.getpixel((x, y)) == H("#2b241c"), C["s5"])
    d.polygon([(0, 132), (60, 126), (120, 134), (180, 126), (260, 132), (260, 150), (0, 150)], fill=C["s2"])
    dither(img, lambda x, y: 124 <= y <= 136 and (x + y) % 2 == 0 and img.getpixel((x, y)) == C["s2"], H("#2b241c"))
    # shrine on the hill: broken colonnade and the fog gate arch
    gx, gy = FIRELINK[-1].point
    d.rectangle((gx - 22, gy + 6, gx + 24, gy + 10), fill=C["d3"])
    for x, h in ((gx - 20, 14), (gx - 14, 9), (gx + 14, 12), (gx + 20, 6)):
        d.rectangle((x, gy + 6 - h, x + 2, gy + 6), fill=C["d4"])
        d.line((x - 1, gy + 6 - h, x + 3, gy + 6 - h), fill=C["d5"])
    d.rectangle((gx - 8, gy - 12, gx + 8, gy + 6), fill=C["d3"])
    d.ellipse((gx - 8, gy - 20, gx + 8, gy - 4), fill=C["d3"])
    d.rectangle((gx - 5, gy - 8, gx + 5, gy + 6), fill=C["out"])
    d.ellipse((gx - 5, gy - 14, gx + 5, gy - 2), fill=C["out"])
    dither(img, lambda x, y: abs(x - gx) <= 4 and gy - 12 <= y <= gy + 5 and (x * 3 + y) % 4 == 0, C["fog2"])
    dither(img, lambda x, y: abs(x - gx) <= 4 and gy - 12 <= y <= gy + 5 and (x + y * 2) % 5 == 0, C["fog"])
    # ruined walls and graves
    for x, y in ((150, 96), (176, 102), (60, 96), (16, 108)):
        d.rectangle((x, y - 6, x + 6, y), fill=C["d3"])
        d.line((x, y - 6, x + 2, y - 8), fill=C["d3"])
        d.point((x + 1, y - 5), C["d5"])
    for x, y in ((80, 138), (88, 140), (200, 128), (210, 131), (232, 126), (150, 140)):
        d.rectangle((x, y - 5, x + 3, y), fill=C["d4"])
        d.point((x + 1, y - 6), C["d4"])
        d.line((x, y - 3, x + 3, y - 3), fill=C["d5"])
    # dead trees
    for x, y, h in ((12, 120, 14), (52, 96, 10), (118, 96, 12), (246, 110, 16), (186, 130, 11), (240, 64, 9)):
        d.line((x, y, x, y - h), fill=C["d1"])
        d.line((x, y - h + 4, x - 4, y - h), fill=C["d1"])
        d.line((x, y - h + 7, x + 4, y - h + 2), fill=C["d1"])
        d.point((x + 1, y - h + 1), C["d1"])
    # moss and stones
    for _ in range(140):
        x, y = rng.randrange(0, W), rng.randrange(96, Hh)
        if img.getpixel((x, y)) in (H("#2b241c"), C["s2"]):
            img.putpixel((x, y), C["moss"] if rng.random() < 0.6 else C["d3"])
    # the path, as ember dots with a dark trodden band
    pts = [n.point for n in FIRELINK]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        steps = max(abs(x1 - x0), abs(y1 - y0))
        for i in range(steps + 1):
            x = round(x0 + (x1 - x0) * i / steps)
            y = round(y0 + (y1 - y0) * i / steps)
            for dx, dy in ((0, 0), (1, 0), (0, 1)):
                if img.getpixel((x + dx, y + dy))[:3] != C["out"][:3]:
                    img.putpixel((x + dx, y + dy), C["s3"])
        for i in range(0, steps, 4):
            x = round(x0 + (x1 - x0) * i / steps)
            y = round(y0 + (y1 - y0) * i / steps)
            img.putpixel((x, y), C["g1"])
    # footing stones under each point
    for x, y in pts[1:-1]:
        d.ellipse((x - 5, y - 1, x + 5, y + 3), fill=C["d2"])
        d.line((x - 4, y + 3, x + 4, y + 3), fill=C["out"])
    # bonfire glow on the ground
    bx, by = FIRELINK[0].point
    dither(img, lambda x, y: (x - bx) ** 2 / 3 + (y - by - 2) ** 2 < 70 and (x + y) % 2 == 0
           and img.getpixel((x, y))[:3] in (C["s2"][:3], H("#2b241c")[:3], C["moss"][:3]), C["e1"])
    # fog over the far east
    dither(img, lambda x, y: x > 200 and y < 70 and x % 3 == 0 and y % 3 == (x // 3) % 3
           and ((x - 236) ** 2 / 3 + (y - 40) ** 2) < 700, C["fog"])
    # vignette
    dither(img, lambda x, y: min(x, y, W - 1 - x, Hh - 1 - y) < 3
           or (min(x, y, W - 1 - x, Hh - 1 - y) < 6 and (x + y) % 2 == 0), C["out"])
    return img


def waypoint(glyph: tuple[int, int, int, int], body: tuple[int, int, int, int]) -> Image.Image:
    """A small rune stone, 12x14."""
    img = Image.new("RGBA", (12, 14), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.polygon([(2, 13), (2, 4), (4, 1), (7, 1), (9, 4), (9, 13)], fill=body)
    d.line((3, 4, 3, 12), fill=C["d5"])
    d.line((5, 5, 6, 5), fill=glyph)
    d.line((5, 5, 5, 9), fill=glyph)
    d.line((5, 9, 7, 9), fill=glyph)
    d.point((7, 7), glyph)
    d.rectangle((1, 12, 10, 13), fill=C["d2"])
    out = img.copy()
    px, src = out.load(), img.load()
    for y in range(14):
        for x in range(12):
            if src[x, y][3]:
                continue
            if any(0 <= x + dx < 12 and 0 <= y + dy < 14 and src[x + dx, y + dy][3]
                   for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                px[x, y] = C["out"]
    return out


def save(img: Image.Image, name: str) -> None:
    w, h = img.size
    img.resize((w * SCALE, h * SCALE), Image.NEAREST).save(OUT / name)


if __name__ == "__main__":
    save(region(), "region_firelink.png")
    save(waypoint(C["e3"], C["d3"]), "waypoint.png")
    save(waypoint(C["g3"], C["d4"]), "waypoint_cleared.png")
    save(waypoint(C["d2"], C["d2"]), "waypoint_locked.png")
