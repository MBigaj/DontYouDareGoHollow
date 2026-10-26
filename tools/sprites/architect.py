"""The Architect road's art (placeholder pixel art): its world map, the Forge, the Strict
Golem and his arena, Data Depths, the Lock Wyrm and his arena, and the road's waypoints.

The Ronin road is warm ember and bone; this road is cold steel, night blue and soul cyan,
with the abyss violet of the Distributed Abyss on the horizon. Drawn at native size and
scaled up with NEAREST, like the Ronin art. Points come from hollow.domain.atlas, so the art
and the pages agree.
Usage: uv run python tools/sprites/architect.py src/hollow/adapters/web/static/sprites
"""

import math
import random
import sys
from collections.abc import Callable
from pathlib import Path

from PIL import Image, ImageDraw

from hollow.domain.atlas import (
    ARCH_POINTS,
    ARCH_WORLD_SIZE,
    DEPTHS,
    DEPTHS_SIZE,
    FORGE,
    FORGE_SIZE,
)

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")

Px = tuple[int, int, int, int]


def H(c: str, a: int = 255) -> Px:
    return (int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16), a)


# From the ASHEN master palette: void, cool steel, night blue, soul cyan, abyss.
C = {k: H(v) for k, v in dict(
    out="#0a080c", v1="#16131a", v2="#221e28",
    sky0="#0b0f1a", n0="#101a2e", n1="#1e3150", n2="#34507a", n3="#5a7fae",
    st0="#1b2230", st1="#2b3646", st2="#3e4c5e", st3="#566a7e", st4="#7a8fa3", st5="#a9bccb",
    cy1="#4fb4d0", cy2="#9ee2ee", cy3="#e6fbff",
    ab0="#1e1430", ab1="#362450", ab2="#563a7a", ab3="#8462a8",
    fog="#3a4656", fog2="#5c6a7c", gold="#b88c3c",
).items()}  # fmt: skip


def dither(img: Image.Image, test: Callable[[int, int], bool], col: Px) -> None:
    px = img.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            if test(x, y):
                px[x, y] = col


def is_(img: Image.Image, x: int, y: int, *cols: Px) -> bool:
    return img.getpixel((x, y))[:3] in [c[:3] for c in cols]


def outline(img: Image.Image) -> Image.Image:
    w, h = img.size
    out = img.copy()
    px, src = out.load(), img.load()
    for y in range(h):
        for x in range(w):
            if src[x, y][3]:
                continue
            if any(0 <= x + dx < w and 0 <= y + dy < h and src[x + dx, y + dy][3]
                   for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                px[x, y] = C["out"]
    return out


def vignette(img: Image.Image, a: int = 3, b: int = 6) -> None:
    w, h = img.size
    dither(img, lambda x, y: min(x, y, w - 1 - x, h - 1 - y) < a
           or (min(x, y, w - 1 - x, h - 1 - y) < b and (x + y) % 2 == 0), C["out"])


def path(img: Image.Image, pts: list[tuple[int, int]], band: Px | None, dot: Px) -> None:
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        steps = max(abs(x1 - x0), abs(y1 - y0))
        if band is not None:
            for i in range(steps + 1):
                x = round(x0 + (x1 - x0) * i / steps)
                y = round(y0 + (y1 - y0) * i / steps)
                for dx, dy in ((0, 0), (1, 0), (0, 1)):
                    if not is_(img, x + dx, y + dy, C["out"]):
                        img.putpixel((x + dx, y + dy), band)
        for i in range(0, steps, 4):
            img.putpixel((round(x0 + (x1 - x0) * i / steps), round(y0 + (y1 - y0) * i / steps)), dot)


# ---------------- the Architect world ----------------
def world() -> Image.Image:
    W, Hh = ARCH_WORLD_SIZE
    img = Image.new("RGBA", (W, Hh), C["sky0"])
    d = ImageDraw.Draw(img)
    rng = random.Random(11)
    y = 0
    for col, hh in ((C["sky0"], 26), (C["n0"], 30), (H("#16223a"), 34), (C["st0"], 135)):
        d.rectangle((0, y, W, y + hh), fill=col)
        y += hh
    for seam, below in ((26, C["n0"]), (56, H("#16223a")), (90, C["st0"])):
        dither(img, lambda x, y, s=seam: s - 2 <= y < s and (x + y) % 2 == 0, below)
    # stars and an aurora of soul light
    for _ in range(70):
        x, y = rng.randrange(W), rng.randrange(0, 60)
        img.putpixel((x, y), C["cy2"] if rng.random() < 0.3 else C["st3"])
    for x in range(W):
        yc = 20 + 7 * math.sin(x / 23) + 3 * math.sin(x / 7)
        for y in range(int(yc) - 3, int(yc) + 4):
            if 0 <= y < Hh and (x + y) % 2 == 0:
                img.putpixel((x, y), C["cy1"] if abs(y - yc) < 1.5 else C["n2"])
    # the abyss: a violet rift with the split islands above it
    ax, ay = ARCH_POINTS["distributed-abyss"]
    for x in range(ax - 60, ax + 61):
        for y in range(ay - 34, ay + 30):
            r = ((x - ax) / 60) ** 2 + ((y - ay + 6) / 30) ** 2
            if r < 0.25:
                img.putpixel((x, y), C["out"])
            elif r < 0.45:
                img.putpixel((x, y), C["ab0"])
            elif r < 0.7 and (x + y) % 2 == 0:
                img.putpixel((x, y), C["ab1"])
            elif r < 1 and x % 2 == 0 and y % 2 == 0:
                img.putpixel((x, y), C["ab2"])
    for ox, oy, flip in ((-22, -12, 1), (14, -16, -1)):
        cx, cy = ax + ox, ay + oy
        d.polygon([(cx - 12, cy), (cx + 12, cy), (cx + 6 * flip, cy + 9), (cx - 4 * flip, cy + 6)],
                  fill=C["st1"])
        d.line((cx - 12, cy, cx + 12, cy), fill=C["st3"])
        d.rectangle((cx - 3, cy - 8, cx + 2, cy), fill=C["st2"])
        d.polygon([(cx - 4, cy - 8), (cx, cy - 13), (cx + 3, cy - 8)], fill=C["st2"])
        img.putpixel((cx, cy - 5), C["ab3"])
    dither(img, lambda x, y: abs(x - ax) < 2 and ay - 18 < y < ay + 4 and y % 2 == 0, C["ab3"])
    # far and mid mountains of steel
    far = [(0, 96), (24, 72), (48, 84), (70, 64), (96, 80), (112, 70), (150, 74), (172, 58),
           (196, 72), (222, 52), (244, 64), (260, 56), (260, 225), (0, 225)]  # fmt: skip
    d.polygon(far, fill=C["st1"])
    dither(img, lambda x, y: 52 <= y <= 100 and (x + y) % 2 == 0 and is_(img, x, y, C["st1"]), C["st0"])
    mid = [(0, 128), (34, 108), (62, 120), (100, 104), (132, 126), (170, 98), (200, 112),
           (236, 90), (260, 100), (260, 225), (0, 225)]  # fmt: skip
    d.polygon(mid, fill=C["st2"])
    dither(img, lambda x, y: y < 132 and x % 2 == 0 and y % 2 == 0 and is_(img, x, y, C["st2"]), C["st1"])
    near = [(0, 160), (50, 150), (100, 160), (150, 148), (200, 150), (260, 140), (260, 225), (0, 225)]
    d.polygon(near, fill=H("#232c3a"))
    dither(img, lambda x, y: 140 <= y <= 164 and (x + y) % 2 == 0 and is_(img, x, y, H("#232c3a")), C["st2"])
    d.polygon([(0, 200), (70, 194), (140, 204), (200, 196), (260, 202), (260, 225), (0, 225)],
              fill=C["st0"])
    # 2. Data Depths: a black lake with database drums sunk in it
    lx, ly = ARCH_POINTS["data-depths"]
    d.ellipse((lx - 30, ly - 6, lx + 30, ly + 16), fill=C["n0"])
    d.ellipse((lx - 26, ly - 4, lx + 26, ly + 13), fill=C["n1"])
    dither(img, lambda x, y: is_(img, x, y, C["n1"]) and y % 3 == 0 and (x // 2 + y) % 4 == 0, C["n2"])
    for dx, h in ((-14, 7), (-3, 11), (9, 6), (18, 4)):
        x0 = lx + dx
        d.rectangle((x0 - 3, ly + 2 - h, x0 + 3, ly + 3), fill=C["st2"])
        d.ellipse((x0 - 3, ly - h, x0 + 3, ly + 4 - h), fill=C["st3"])
        d.line((x0 - 3, ly + 1 - h // 2, x0 + 3, ly + 1 - h // 2), fill=C["st1"])
        img.putpixel((x0 + 1, ly + 2 - h), C["cy2"])
    # 3. The API Citadel: walls, towers and one bright gate
    cx, cy = ARCH_POINTS["api-citadel"]
    d.rectangle((cx - 20, cy - 10, cx + 20, cy + 2), fill=C["st1"])
    for x in range(cx - 20, cx + 21, 4):
        d.rectangle((x, cy - 13, x + 1, cy - 10), fill=C["st1"])
    for tx in (cx - 22, cx + 16):
        d.rectangle((tx, cy - 22, tx + 6, cy + 2), fill=C["st2"])
        d.polygon([(tx - 1, cy - 22), (tx + 3, cy - 28), (tx + 7, cy - 22)], fill=C["st3"])
        img.putpixel((tx + 3, cy - 16), C["cy2"])
    d.rectangle((cx - 4, cy - 7, cx + 4, cy + 2), fill=C["out"])
    dither(img, lambda x, y: abs(x - cx) <= 3 and cy - 6 <= y <= cy + 1 and (x + y) % 2 == 0, C["cy1"])
    # 4. The Async Ruins: broken arches, with stray messages hanging in the air
    rx, ry = ARCH_POINTS["async-ruins"]
    for ox, h in ((-18, 16), (-8, 10), (4, 18), (14, 7)):
        d.rectangle((rx + ox, ry - h, rx + ox + 3, ry + 2), fill=C["st2"])
        d.line((rx + ox, ry - h, rx + ox + 3, ry - h), fill=C["st4"])
    d.arc((rx - 18, ry - 24, rx - 5, ry - 8), 180, 300, fill=C["st2"], width=2)
    for mx, my in ((rx - 12, ry - 30), (rx + 4, ry - 34), (rx + 16, ry - 22)):
        d.rectangle((mx, my, mx + 4, my + 3), fill=C["st4"])
        d.line((mx, my, mx + 2, my + 2), fill=C["st2"])
        d.line((mx + 4, my, mx + 2, my + 2), fill=C["st2"])
    # 5. The Watchtower: tall, with a lantern that sees everything
    wx, wy = ARCH_POINTS["watchtower"]
    d.polygon([(wx - 5, wy + 2), (wx - 3, wy - 34), (wx + 3, wy - 34), (wx + 5, wy + 2)], fill=C["st2"])
    d.line((wx - 3, wy - 34, wx - 4, wy + 2), fill=C["st4"])
    d.rectangle((wx - 6, wy - 40, wx + 6, wy - 34), fill=C["st1"])
    d.polygon([(wx - 7, wy - 40), (wx, wy - 47), (wx + 7, wy - 40)], fill=C["st3"])
    d.rectangle((wx - 2, wy - 39, wx + 2, wy - 36), fill=C["cy3"])
    dither(img, lambda x, y: wy - 44 < y < wy - 30 and 8 < abs(x - wx) < 40 - abs(y - wy + 37) * 2
           and (x + 2 * y) % 5 == 0 and not is_(img, x, y, C["out"]), C["n3"])
    # 6. The Iron Keep: square iron, chimneys and smoke
    kx, ky = ARCH_POINTS["iron-keep"]
    d.rectangle((kx - 16, ky - 20, kx + 16, ky + 2), fill=C["st1"])
    d.rectangle((kx - 8, ky - 30, kx + 8, ky - 20), fill=C["st2"])
    for x in range(kx - 16, kx + 17, 4):
        d.rectangle((x, ky - 23, x + 1, ky - 20), fill=C["st1"])
    for x in (kx - 12, kx + 10):
        d.rectangle((x, ky - 28, x + 2, ky - 20), fill=C["st3"])
        for i in range(5):
            img.putpixel((x + 1 + i % 2, ky - 30 - i * 2), C["fog2"])
    for x, y in ((kx - 10, ky - 12), (kx - 2, ky - 14), (kx + 6, ky - 12), (kx - 4, ky - 26)):
        d.rectangle((x, y, x + 1, y + 2), fill=C["cy1"])
    # 7. The Undercroft: a cave mouth with cables running into the dark
    ux, uy = ARCH_POINTS["undercroft"]
    cliff = [(ux - 24, uy + 3), (ux - 14, uy - 18), (ux + 8, uy - 23), (ux + 24, uy + 3)]
    d.polygon(cliff, fill=C["st1"])
    d.line(cliff[:3], fill=C["st3"])
    dither(img, lambda x, y: is_(img, x, y, C["st1"]) and abs(x - ux) < 24 and uy - 22 < y < uy + 3
           and (x + y) % 2 == 0 and x > ux + 4, C["st0"])
    d.ellipse((ux - 9, uy - 12, ux + 9, uy + 8), fill=C["out"])
    d.rectangle((ux - 9, uy - 2, ux + 9, uy + 2), fill=C["out"])
    for i, col in enumerate((C["cy1"], C["st4"], C["n3"])):
        d.line((ux - 24 + i * 3, uy + 4, ux - 4 + i * 2, uy - 2 + i), fill=col)
    for x, y in ((ux - 2, uy - 4), (ux + 3, uy - 2)):
        img.putpixel((x, y), C["cy2"])
    # 1. The Forge: a squat stone forge breathing soul-fire
    fx, fy = ARCH_POINTS["forge"]
    d.rectangle((fx - 12, fy - 12, fx + 12, fy + 2), fill=C["st2"])
    d.polygon([(fx - 14, fy - 12), (fx, fy - 20), (fx + 14, fy - 12)], fill=C["st3"])
    d.rectangle((fx + 6, fy - 26, fx + 10, fy - 16), fill=C["st2"])
    d.rectangle((fx - 5, fy - 6, fx + 5, fy + 2), fill=C["out"])
    dither(img, lambda x, y: abs(x - fx) <= 4 and fy - 5 <= y <= fy + 1 and (x + y) % 2 == 0, C["cy1"])
    for i in range(6):
        img.putpixel((fx + 8 + (i % 2), fy - 28 - i * 2), C["cy2"] if i < 2 else C["fog2"])
    dither(img, lambda x, y: (x - fx) ** 2 / 3 + (y - fy - 4) ** 2 < 90 and (x + y) % 2 == 0
           and is_(img, x, y, C["st0"], H("#232c3a")), C["n2"])
    # little ruins and iron posts across the land
    for _ in range(26):
        x, y = rng.randrange(8, W - 8), rng.randrange(150, 215)
        if is_(img, x, y, H("#232c3a"), C["st0"]):
            d.rectangle((x, y - 4, x + 1, y), fill=C["st3"])
            img.putpixel((x, y - 5), C["st4"])
    # the road, in soul-cyan dots
    road = [ARCH_POINTS[k] for k in ARCH_POINTS]
    path(img, road, None, C["cy1"])
    # mist over the lands beyond the Forge
    dither(img, lambda x, y: x > 70 and y < 205 and x % 3 == 0 and y % 3 == (x // 3) % 3
           and ((x - 160) ** 2 / 5 + (y - 120) ** 2) < 3800, C["fog"])
    vignette(img, 4, 8)
    return img


# ---------------- the Forge ----------------
def forge() -> Image.Image:
    W, Hh = FORGE_SIZE
    img = Image.new("RGBA", (W, Hh), C["out"])
    d = ImageDraw.Draw(img)
    rng = random.Random(5)
    # the back wall: riveted iron plates
    d.rectangle((0, 0, W, 70), fill=C["st0"])
    for row, y in enumerate(range(8, 70, 10)):
        d.line((0, y, W, y), fill=C["v1"])
        for x in range(0 if row % 2 else 10, W, 20):
            d.line((x, y, x, y + 9), fill=C["v1"])
            img.putpixel((x + 2, y + 2), C["st2"])
    dither(img, lambda x, y: y < 18 and (x + y) % 2 == 0, C["out"])
    # pipes
    for x in (18, 70, 176, 248):
        d.rectangle((x, 0, x + 3, 64), fill=C["st2"])
        d.line((x, 0, x, 64), fill=C["st3"])
        for y in range(10, 64, 14):
            d.rectangle((x - 1, y, x + 4, y + 1), fill=C["st3"])
    d.rectangle((0, 22, 260, 24), fill=C["st1"])
    # soul furnaces breathing cyan into the hall
    for fx in (44, 104, 150):
        d.rectangle((fx - 10, 26, fx + 10, 62), fill=C["st1"])
        d.polygon([(fx - 12, 26), (fx, 18), (fx + 12, 26)], fill=C["st2"])
        d.ellipse((fx - 6, 36, fx + 6, 50), fill=C["out"])
        d.rectangle((fx - 6, 43, fx + 6, 58), fill=C["out"])
        dither(img, lambda x, y, f=fx: abs(x - f) <= 5 and 40 <= y <= 57
               and (x + y) % 2 == 0, C["cy1"])
        dither(img, lambda x, y, f=fx: abs(x - f) <= 2 and 46 <= y <= 56, C["cy2"])
        img.putpixel((fx, 50), C["cy3"])
        dither(img, lambda x, y, f=fx: 0 < (x - f) ** 2 + (y - 48) ** 2 < 420 and (x * 2 + y) % 4 == 0
               and is_(img, x, y, C["st0"], C["v1"]), C["n1"])
    # chains from the dark
    for x, length in ((32, 26), (84, 18), (126, 30), (198, 22)):
        for y in range(0, length, 3):
            d.rectangle((x, y, x + 1, y + 1), fill=C["st3"] if y % 6 else C["st2"])
        d.polygon([(x - 2, length), (x + 3, length), (x + 1, length + 4)], fill=C["st3"])
    # the boss door: a great iron gate with fog in it
    gx, gy = FORGE[-1].point
    d.rectangle((gx - 16, gy - 30, gx + 16, gy + 8), fill=C["st1"])
    d.ellipse((gx - 16, gy - 40, gx + 16, gy - 20), fill=C["st1"])
    d.rectangle((gx - 11, gy - 26, gx + 11, gy + 8), fill=C["out"])
    d.ellipse((gx - 11, gy - 34, gx + 11, gy - 16), fill=C["out"])
    for y in range(gy - 26, gy + 8, 6):
        img.putpixel((gx - 14, y), C["st4"])
        img.putpixel((gx + 14, y), C["st4"])
    dither(img, lambda x, y: abs(x - gx) <= 10 and gy - 30 <= y <= gy + 7 and (x * 3 + y) % 4 == 0
           and is_(img, x, y, C["out"]), C["fog2"])
    dither(img, lambda x, y: abs(x - gx) <= 10 and gy - 30 <= y <= gy + 7 and (x + y * 2) % 5 == 0
           and is_(img, x, y, C["out"]), C["fog"])
    # the floor: iron plates receding
    d.polygon([(0, 62), (260, 52), (260, 150), (0, 150)], fill=C["st1"])
    for y in (70, 82, 98, 118, 142):
        d.line((0, y + (8 if y < 90 else 0) - 8, 260, y - (2 if y < 90 else 0)), fill=C["st0"])
    for x in range(-300, 600, 40):
        d.line((130, 40, x, 150), fill=C["st0"])
    d.polygon([(0, 62), (260, 52), (260, 56), (0, 66)], fill=C["st2"])
    dither(img, lambda x, y: 56 <= y <= 72 and (x + y) % 2 == 0 and is_(img, x, y, C["st1"]), C["st0"])
    # a channel of molten soul-metal across the floor
    for x in range(0, W):
        yc = 136 - 10 * math.sin(x / 34) - x / 26
        for y in range(int(yc) - 3, int(yc) + 3):
            if 0 <= y < Hh:
                img.putpixel((x, y), C["cy1"] if abs(y - yc) < 1.3 else C["n2"])
        if x % 5 == 0:
            img.putpixel((x, int(yc)), C["cy3"])
    # anvils and crates
    for ax, ay in ((40, 136), (150, 120), (226, 128), (70, 86), (176, 64)):
        d.rectangle((ax - 5, ay - 4, ax + 5, ay - 2), fill=C["st3"])
        d.line((ax - 7, ay - 4, ax + 6, ay - 4), fill=C["st4"])
        d.rectangle((ax - 2, ay - 2, ax + 2, ay + 1), fill=C["st2"])
        d.rectangle((ax - 4, ay + 1, ax + 4, ay + 2), fill=C["st2"])
    for _ in range(60):
        x, y = rng.randrange(0, W), rng.randrange(66, Hh)
        if is_(img, x, y, C["st1"]):
            img.putpixel((x, y), C["st2"])
    # the path, with footing plates
    pts = [n.point for n in FORGE]
    path(img, pts, C["st0"], C["cy1"])
    for x, y in pts[1:-1]:
        d.ellipse((x - 5, y - 1, x + 5, y + 3), fill=C["st2"])
        d.line((x - 4, y + 3, x + 4, y + 3), fill=C["out"])
    bx, by = FORGE[0].point
    dither(img, lambda x, y: (x - bx) ** 2 / 3 + (y - by - 2) ** 2 < 70 and (x + y) % 2 == 0
           and is_(img, x, y, C["st1"], C["st0"]), C["n2"])
    vignette(img)
    return img


# ---------------- the Strict Golem ----------------
OPEN = [".##", ".#.", "#..", ".#.", ".##"]
"""A brace, drawn on the golem's core twice: { and its mirror }."""


def golem() -> Image.Image:
    img = Image.new("RGBA", (72, 84), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # legs
    for x in (20, 40):
        d.rectangle((x, 58, x + 11, 82), fill=C["st2"])
        d.line((x + 1, 58, x + 1, 80), fill=C["st3"])
        d.rectangle((x - 2, 76, x + 13, 83), fill=C["st1"])
        dither(img, lambda xx, yy, x0=x: x0 + 6 <= xx <= x0 + 11 and 58 <= yy <= 76
               and (xx + yy) % 2 == 0, C["st1"])
    # torso
    d.polygon([(12, 22), (60, 22), (54, 60), (18, 60)], fill=C["st2"])
    d.line((13, 23, 19, 59), fill=C["st4"])
    dither(img, lambda x, y: x > 38 and 22 <= y <= 60 and (x + y) % 2 == 0
           and is_(img, x, y, C["st2"]), C["st1"])
    for y in (32, 44):
        d.line((16, y, 56, y), fill=C["st1"])
    for x, y in ((18, 26), (52, 26), (20, 54), (50, 54), (35, 25)):
        img.putpixel((x, y), C["st5"])
    # the core: a cyan furnace marked with braces
    d.ellipse((27, 30, 45, 48), fill=C["out"])
    d.ellipse((29, 32, 43, 46), fill=C["n1"])
    dither(img, lambda x, y: (x - 36) ** 2 + (y - 39) ** 2 < 36 and (x + y) % 2 == 0, C["cy1"])
    for dy, row in enumerate(OPEN):
        for dx, ch in enumerate(row):
            if ch == "#":
                img.putpixel((31 + dx, 37 + dy), C["cy3"])
                img.putpixel((40 - dx, 37 + dy), C["cy3"])
    # shoulders and arms ending in great fists
    for x0, flip in ((2, 1), (54, -1)):
        d.ellipse((x0, 16, x0 + 16, 32), fill=C["st3"])
        d.line((x0 + 3, 17, x0 + 12, 17), fill=C["st5"])
        dither(img, lambda x, y, a=x0: a <= x <= a + 16 and 25 <= y <= 32 and (x + y) % 2 == 0
               and is_(img, x, y, C["st3"]), C["st2"])
        d.rectangle((x0 + 4, 30, x0 + 12, 52), fill=C["st2"])
        d.line((x0 + 5, 30, x0 + 5, 52), fill=C["st3"])
        d.rectangle((x0 + 1, 52, x0 + 15, 64), fill=C["st3"])
        d.line((x0 + 1, 56, x0 + 15, 56), fill=C["st1"])
        d.line((x0 + 1, 60, x0 + 15, 60), fill=C["st1"])
        img.putpixel((x0 + 8 + 3 * flip, 53), C["st5"])
    # head: a narrow helm with a visor slit
    d.rectangle((26, 4, 46, 22), fill=C["st3"])
    d.polygon([(26, 4), (36, 0), (46, 4)], fill=C["st4"])
    d.line((27, 5, 27, 21), fill=C["st5"])
    dither(img, lambda x, y: x > 38 and 4 <= y <= 22 and (x + y) % 2 == 0
           and is_(img, x, y, C["st3"]), C["st2"])
    d.rectangle((29, 11, 43, 14), fill=C["out"])
    for x in (31, 32, 40, 41):
        img.putpixel((x, 12), C["cy2"])
    img.putpixel((32, 13), C["cy1"])
    img.putpixel((40, 13), C["cy1"])
    return outline(img)


# ---------------- the Golem's arena ----------------
def arena() -> Image.Image:
    W, Hh = 360, 225
    img = Image.new("RGBA", (W, Hh), C["out"])
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, W, 150), fill=C["st0"])
    for row, y in enumerate(range(0, 150, 8)):
        d.line((0, y, W, y), fill=C["v1"])
        for x in range(0 if row % 2 else 8, W, 16):
            d.line((x, y, x, y + 7), fill=C["v1"])
    dither(img, lambda x, y: y < 50 and (x + y) % 2 == 0, C["v1"])
    dither(img, lambda x, y: y < 18 and x % 2 == 0, C["out"])
    # the great furnace behind the golem
    d.rectangle((70, 40, 190, 150), fill=C["v1"])
    d.ellipse((70, 10, 190, 80), fill=C["v1"])
    d.arc((66, 6, 194, 84), 180, 360, fill=C["st3"], width=4)
    d.rectangle((66, 45, 69, 150), fill=C["st3"])
    d.rectangle((191, 45, 194, 150), fill=C["st3"])
    for x in range(80, 181):
        for y in range(70, 150):
            r = ((x - 130) / 50) ** 2 + ((y - 150) / 70) ** 2
            if r < 0.35 and (x + y) % 2 == 0:
                img.putpixel((x, y), C["cy1"])
            elif r < 0.7 and (x + y) % 3 == 0:
                img.putpixel((x, y), C["n2"])
            elif r < 1 and x % 2 == 0 and y % 2 == 0:
                img.putpixel((x, y), C["n1"])
    # pipe pillars
    for x0 in (16, 222, 300):
        d.rectangle((x0, 20, x0 + 14, 160), fill=C["st1"])
        d.line((x0 + 2, 20, x0 + 2, 158), fill=C["st3"])
        dither(img, lambda x, y, a=x0: a + 8 <= x <= a + 14 and 20 <= y <= 160 and (x + y) % 2 == 0, C["st0"])
        for y in range(30, 160, 22):
            d.rectangle((x0 - 2, y, x0 + 16, y + 3), fill=C["st2"])
        d.rectangle((x0 + 4, 60, x0 + 10, 66), fill=C["out"])
        d.rectangle((x0 + 5, 61, x0 + 9, 65), fill=C["cy1"])
        img.putpixel((x0 + 7, 63), C["cy3"])
    # the floor
    d.rectangle((0, 150, W, Hh), fill=C["st1"])
    for y in (156, 166, 180, 198, 220):
        d.line((0, y, W, y), fill=C["st0"])
    for x in range(-400, 800, 50):
        d.line((140, 150, x, Hh), fill=C["st0"])
    dither(img, lambda x, y: 150 <= y <= 158 and (x + y) % 2 == 0, C["st2"])
    dither(img, lambda x, y: 152 <= y <= 176 and x % 3 == 0 and y % 3 == (x // 3) % 3
           and ((x - 140) ** 2 / 9 + (y - 162) ** 2 * 4) < 2400, C["n1"])
    vignette(img, 4, 10)
    return img


# ---------------- Data Depths ----------------
def tablet(d: ImageDraw.ImageDraw, x: int, y: int, ghost: bool) -> None:
    """A stone row-tablet on a vault shelf; ghosts are the old versions vacuum has not taken."""
    if ghost:
        for yy in range(y, y + 6):
            for xx in range(x, x + 9):
                if (xx + yy) % 2 == 0:
                    d.point((xx, yy), C["n1"])
        return
    d.rectangle((x, y, x + 8, y + 5), fill=C["st2"])
    d.line((x, y, x + 8, y), fill=C["st4"])
    d.line((x + 2, y + 2, x + 6, y + 2), fill=C["st1"])
    d.point((x + 1, y + 4), C["cy1"])


def depths() -> Image.Image:
    W, Hh = DEPTHS_SIZE
    img = Image.new("RGBA", (W, Hh), C["out"])
    d = ImageDraw.Draw(img)
    rng = random.Random(11)
    # the vault: a row of arches, each holding shelves of tablets and their ghost versions
    d.rectangle((0, 0, W, 64), fill=C["v1"])
    for ax in range(-10, W + 40, 40):
        d.rectangle((ax + 4, 8, ax + 36, 64), fill=C["v2"])
        d.ellipse((ax + 4, 0, ax + 36, 18), fill=C["v2"])
        d.arc((ax + 2, -2, ax + 38, 20), 180, 360, fill=C["st2"], width=2)
        d.rectangle((ax, 6, ax + 3, 64), fill=C["st1"])
        d.line((ax + 1, 6, ax + 1, 64), fill=C["st3"])
        for row, sy in enumerate(range(16, 58, 9)):
            d.line((ax + 5, sy + 6, ax + 35, sy + 6), fill=C["st1"])
            for k, tx in enumerate(range(ax + 6, ax + 32, 10)):
                tablet(d, tx, sy, ghost=(row * 3 + k + ax // 40) % 4 == 0)
    dither(img, lambda x, y: y < 14 and (x + y) % 2 == 0, C["out"])
    # the waterline and the flood below it
    d.rectangle((0, 62, W, Hh), fill=C["n0"])
    dither(img, lambda x, y: y > 62 and (x * 3 + y * 5) % 7 == 0, C["sky0"])
    dither(img, lambda x, y: 62 <= y <= 66 and (x + y) % 2 == 0, C["n1"])
    for _ in range(120):
        x, y = rng.randrange(0, W - 6), rng.randrange(68, Hh)
        d.line((x, y, x + rng.randrange(2, 6), y), fill=C["n1"] if y % 3 else C["n2"])
    # drowned pillars, with their reflections broken by the water
    for px_ in (12, 64, 136, 244):
        d.rectangle((px_, 6, px_ + 7, 66), fill=C["st1"])
        d.line((px_ + 1, 6, px_ + 1, 66), fill=C["st3"])
        dither(img, lambda x, y, a=px_: a + 4 <= x <= a + 7 and 6 <= y <= 66 and (x + y) % 2 == 0,
               C["st0"])
        dither(img, lambda x, y, a=px_: a <= x <= a + 7 and 67 <= y <= 92 and y % 3 != 0
               and (x + y) % 2 == 0, C["st0"])
    # the causeways between the walkway stones, then the path itself
    pts = [n.point for n in DEPTHS]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        steps = max(abs(x1 - x0), abs(y1 - y0))
        for i in range(steps + 1):
            x = round(x0 + (x1 - x0) * i / steps)
            y = round(y0 + (y1 - y0) * i / steps)
            if y > 60:
                d.rectangle((x - 2, y - 1, x + 3, y + 3), fill=C["st1"])
                img.putpixel((x, y + 4), C["n1"])
    path(img, pts, C["st2"], C["cy1"])
    for x, y in pts[1:-1]:
        d.ellipse((x - 6, y - 1, x + 6, y + 4), fill=C["st2"])
        d.line((x - 5, y - 1, x + 5, y - 1), fill=C["st4"])
        d.line((x - 5, y + 4, x + 5, y + 4), fill=C["out"])
        dither(img, lambda xx, yy, a=x, b=y: abs(xx - a) <= 7 and b + 5 <= yy <= b + 7
               and (xx + yy) % 2 == 0, C["cy1"])
    # the boss door: a round vault door, bolted and chained shut, fog seeping round it
    gx, gy = DEPTHS[-1].point
    d.ellipse((gx - 19, gy - 34, gx + 19, gy + 4), fill=C["st1"])
    d.ellipse((gx - 15, gy - 30, gx + 15, gy), fill=C["st2"])
    d.ellipse((gx - 9, gy - 24, gx + 9, gy - 6), fill=C["st1"])
    for a in range(0, 360, 45):
        bx = gx + round(12 * math.cos(math.radians(a)))
        by = gy - 15 + round(12 * math.sin(math.radians(a)))
        d.rectangle((bx - 1, by - 1, bx + 1, by + 1), fill=C["st4"])
    for i in range(-14, 15, 3):
        d.rectangle((gx + i, gy - 15 + i // 2, gx + i + 1, gy - 14 + i // 2), fill=C["st4"])
    d.rectangle((gx - 3, gy - 13, gx + 3, gy - 7), fill=C["st4"])
    d.arc((gx - 3, gy - 18, gx + 3, gy - 10), 180, 360, fill=C["st4"])
    img.putpixel((gx, gy - 10), C["cy2"])
    dither(img, lambda x, y: 14 < (x - gx) ** 2 / 1.4 + (y - gy + 15) ** 2 / 1.2 < 520
           and (x * 3 + y) % 5 == 0 and is_(img, x, y, C["v1"], C["v2"], C["n0"]), C["fog2"])
    # the bonfire's glow on the water
    bx, by = DEPTHS[0].point
    dither(img, lambda x, y: (x - bx) ** 2 / 3 + (y - by - 2) ** 2 < 80 and (x + y) % 2 == 0
           and is_(img, x, y, C["n0"], C["sky0"], C["n1"]), C["n2"])
    vignette(img)
    return img


# ---------------- the Lock Wyrm ----------------
def wyrm() -> Image.Image:
    """Coils of night-blue scale bound in steel chains, a padlock at the front, cyan eyes."""
    img = Image.new("RGBA", (80, 84), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def coil(cx: int, cy: int, rx: int, ry: int) -> None:
        d.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=C["n1"])
        d.arc((cx - rx, cy - ry, cx + rx, cy + ry), 190, 350, fill=C["n3"])
        d.arc((cx - rx + 2, cy - ry + 2, cx + rx - 2, cy + ry - 2), 200, 340, fill=C["n2"])
        d.arc((cx - rx, cy - ry, cx + rx, cy + ry), 20, 160, fill=C["st2"], width=2)
        dither(img, lambda x, y: (x - cx) ** 2 / rx**2 + (y - cy) ** 2 / ry**2 < 0.8
               and (x + 2 * y) % 5 == 0 and is_(img, x, y, C["n1"]), C["n2"])
        dither(img, lambda x, y: x > cx + rx // 3 and (x - cx) ** 2 / rx**2
               + (y - cy) ** 2 / ry**2 < 1 and (x + y) % 2 == 0 and is_(img, x, y, C["n1"]),
               C["n0"])

    # the tail curls out to the left, then three coils, largest at the bottom
    for i in range(14):
        tx, ty = 4 + i * 2, 78 - round(3 * math.sin(i / 2.5))
        r = 1 + i // 5
        d.ellipse((tx - r, ty - r, tx + r, ty + r), fill=C["n1"])
    coil(42, 70, 34, 12)
    coil(42, 58, 27, 10)
    coil(40, 47, 20, 8)
    # the neck rises from the top coil to the head, with a crest of steel fins
    for i in range(22):
        t = i / 21
        nx = round(46 - 6 * t + 8 * math.sin(t * 3))
        ny = round(44 - 28 * t)
        r = 6 - round(2 * t)
        d.ellipse((nx - r, ny - r, nx + r, ny + r), fill=C["n1"])
        img.putpixel((nx - r + 1, ny), C["n3"])
        if i % 4 == 0:
            d.polygon([(nx + r - 1, ny - 1), (nx + r + 4, ny - 3), (nx + r, ny + 2)], fill=C["st3"])
    # the head, facing left towards the knight
    d.polygon([(22, 16), (32, 10), (46, 8), (54, 13), (52, 21), (40, 24), (26, 22)], fill=C["n1"])
    d.line((32, 10, 46, 8), fill=C["n3"])
    d.polygon([(22, 18), (34, 20), (26, 24)], fill=C["out"])
    dither(img, lambda x, y: 24 <= x <= 32 and 19 <= y <= 22 and (x + y) % 2 == 0
           and is_(img, x, y, C["out"]), C["cy1"])
    d.line((44, 8, 56, 2), fill=C["st4"])
    d.line((48, 10, 60, 6), fill=C["st3"])
    d.rectangle((36, 13, 39, 15), fill=C["out"])
    img.putpixel((37, 14), C["cy3"])
    img.putpixel((38, 14), C["cy2"])
    img.putpixel((23, 16), C["n3"])
    # chains across the coils, and the padlock that keeps them shut
    for y0, y1 in ((60, 78), (50, 66), (42, 56)):
        steps = 26
        for i in range(0, steps, 2):
            x = 14 + round(56 * i / steps)
            y = round(y0 + (y1 - y0) * i / steps)
            d.rectangle((x, y, x + 2, y + 1), fill=C["st4"] if i % 4 else C["st3"])
            img.putpixel((x + 1, y), C["st5"])
    d.rectangle((36, 70, 46, 79), fill=C["st3"])
    d.line((36, 70, 46, 70), fill=C["st5"])
    d.arc((37, 63, 45, 73), 180, 360, fill=C["st4"], width=2)
    d.rectangle((40, 73, 42, 76), fill=C["out"])
    img.putpixel((41, 74), C["cy2"])
    return outline(img)


# ---------------- the Wyrm's arena ----------------
def depths_arena() -> Image.Image:
    W, Hh = 360, 225
    img = Image.new("RGBA", (W, Hh), C["out"])
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, W, 150), fill=C["v1"])
    # arches and shelves of row-tablets on the left
    for ax in (-8, 60, 130):
        d.rectangle((ax + 6, 30, ax + 58, 150), fill=C["v2"])
        d.ellipse((ax + 6, 6, ax + 58, 54), fill=C["v2"])
        d.arc((ax + 4, 4, ax + 60, 56), 180, 360, fill=C["st2"], width=3)
        for row, sy in enumerate(range(40, 140, 12)):
            d.line((ax + 8, sy + 8, ax + 56, sy + 8), fill=C["st1"])
            for k, tx in enumerate(range(ax + 10, ax + 50, 13)):
                tablet(d, tx, sy, ghost=(row + k) % 3 == 0)
    # the great vault door behind the wyrm, its bolts glowing
    cx, cy = 266, 90
    d.ellipse((cx - 66, cy - 66, cx + 66, cy + 66), fill=C["st0"])
    d.ellipse((cx - 58, cy - 58, cx + 58, cy + 58), fill=C["st1"])
    d.ellipse((cx - 36, cy - 36, cx + 36, cy + 36), fill=C["st0"])
    for a in range(0, 360, 30):
        bx = cx + round(47 * math.cos(math.radians(a)))
        by = cy + round(47 * math.sin(math.radians(a)))
        d.rectangle((bx - 3, by - 3, bx + 3, by + 3), fill=C["st3"])
        d.rectangle((bx - 1, by - 1, bx + 1, by + 1), fill=C["cy1"])
    dither(img, lambda x, y: (x - cx) ** 2 + (y - cy) ** 2 < 1200 and (x + y) % 2 == 0, C["n0"])
    dither(img, lambda x, y: (x - cx) ** 2 + (y - cy) ** 2 < 400 and (x + y) % 3 == 0, C["n1"])
    # pillars in front of everything on the back wall
    for x0 in (0, 54, 124, 192, 344):
        d.rectangle((x0, 0, x0 + 8, 160), fill=C["st1"])
        d.line((x0 + 1, 0, x0 + 1, 160), fill=C["st3"])
        dither(img, lambda x, y, a=x0: a + 5 <= x <= a + 8 and (x + y) % 2 == 0, C["st0"])
    # hanging chains
    for x, length in ((34, 50), (104, 34), (176, 60), (326, 44)):
        for y in range(0, length, 3):
            d.rectangle((x, y, x + 1, y + 1), fill=C["st3"] if y % 6 else C["st2"])
    dither(img, lambda x, y: y < 20 and (x + y) % 2 == 0, C["out"])
    # the flooded floor: a stone dais in dark water
    d.rectangle((0, 148, W, Hh), fill=C["n0"])
    dither(img, lambda x, y: y > 148 and (x * 3 + y * 5) % 7 == 0, C["sky0"])
    dither(img, lambda x, y: 148 <= y <= 151 and (x + y) % 2 == 0, C["n2"])
    rng = random.Random(3)
    for _ in range(140):
        x, y = rng.randrange(0, W - 8), rng.randrange(152, Hh)
        d.line((x, y, x + rng.randrange(3, 8), y), fill=C["n1"] if y % 3 else C["n2"])
    d.polygon([(20, 176), (340, 168), (356, 212), (4, 222)], fill=C["st1"])
    dais = Image.new("RGBA", (W, Hh), (0, 0, 0, 0))
    g = ImageDraw.Draw(dais)
    for y in (186, 198, 212):
        g.line((10, y + 6, 350, y - 2), fill=C["st0"])
    for x in range(-200, 700, 46):
        g.line((180, 150, x, Hh), fill=C["st0"])
    lines = dais.load()
    for y in range(Hh):
        for x in range(W):
            if lines[x, y][3] and is_(img, x, y, C["st1"]):
                img.putpixel((x, y), C["st0"])
    d.line((20, 176, 340, 168), fill=C["st3"])
    dither(img, lambda x, y: 168 <= y <= 180 and (x + y) % 2 == 0 and is_(img, x, y, C["st1"]),
           C["st2"])
    vignette(img, 4, 10)
    return img


def chain_icon() -> Image.Image:
    """The Lock Wyrm's Chain, a 16x16 item like the Ronin road's icons."""
    img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i, (x, y) in enumerate(((1, 12), (4, 9), (7, 6), (10, 3))):
        if i % 2:
            d.rectangle((x, y, x + 3, y + 2), outline=C["st4"])
        else:
            d.rectangle((x, y, x + 2, y + 3), outline=C["st3"])
    d.rectangle((10, 8, 15, 14), fill=C["st3"])
    d.line((10, 8, 15, 8), fill=C["st5"])
    d.arc((10, 4, 15, 10), 180, 360, fill=C["st4"])
    img.putpixel((12, 11), C["cy2"])
    img.putpixel((12, 12), C["out"])
    padded = Image.new("RGBA", (18, 18), (0, 0, 0, 0))
    padded.paste(img, (1, 1))
    return outline(padded)


# ---------------- the road's waypoints ----------------
def waypoint(glyph: Px, body: Px, edge: Px) -> Image.Image:
    """A small iron obelisk with a cyan seam, 12x14 (the Ronin road uses rune stones)."""
    img = Image.new("RGBA", (12, 14), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.polygon([(3, 13), (3, 3), (6, 0), (8, 3), (8, 13)], fill=body)
    d.line((4, 3, 4, 12), fill=edge)
    d.line((6, 3, 6, 10), fill=glyph)
    img.putpixel((7, 5), glyph)
    img.putpixel((5, 8), glyph)
    d.rectangle((1, 12, 10, 13), fill=C["st1"])
    return outline(img)


def save(img: Image.Image, name: str, scale: int) -> None:
    w, h = img.size
    img.resize((w * scale, h * scale), Image.NEAREST).save(OUT / name)


if __name__ == "__main__":
    save(world(), "map_architect.png", 4)
    save(forge(), "region_forge.png", 4)
    save(golem(), "golem_body.png", 6)
    save(arena(), "arena_forge.png", 4)
    save(depths(), "region_data_depths.png", 4)
    save(wyrm(), "wyrm_body.png", 6)
    save(depths_arena(), "arena_data_depths.png", 4)
    save(chain_icon(), "item_chain.png", 3)
    save(waypoint(C["cy1"], C["st2"], C["st4"]), "waypoint_arch.png", 4)
    save(waypoint(C["cy3"], C["st3"], C["st5"]), "waypoint_arch_cleared.png", 4)
    save(waypoint(C["st1"], C["st1"], C["st2"]), "waypoint_arch_locked.png", 4)
