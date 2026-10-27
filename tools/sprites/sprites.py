"""Procedural pixel-art sprites for DontYouDareGoHollow: item icons, the slash and the anvil.

Draws each sprite at native size, outlines it and scales it up with NEAREST.
Usage: uv run --with pillow python tools/sprites/sprites.py src/hollow/adapters/web/static/sprites
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)


def H(c, a=255):
    return tuple(int(c[i : i + 2], 16) for i in (1, 3, 5)) + (a,)


C = {
    k: H(v)
    for k, v in dict(
        out="#0b0a08",
        d0="#120f0c",
        d1="#1a1612",
        d2="#2a231b",
        d3="#3a3025",
        d4="#5a4e3e",
        d5="#8c7f69",
        l1="#c9bfa9",
        l2="#f1e6d0",
        e1="#7a3510",
        e2="#c2611f",
        e3="#e9a15f",
        e4="#ffe2bf",
        r1="#5a1a12",
        r2="#a3241a",
        r3="#e07560",
        b1="#1f3346",
        b2="#34506a",
        b3="#7fa7c9",
        b4="#d8e7f3",
        g1="#8a6a34",
        g2="#c9a86a",
        g3="#e9c27a",
        c1="#3a1c15",
        c2="#5a2e22",
        c3="#8a4b36",
        s1="#14120f",
        s2="#1c1814",
        s3="#231d17",
        s4="#2e261e",
        s5="#3b3127",
    ).items()
}


def new(w, h, bg=None):
    img = Image.new("RGBA", (w, h), bg or (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


def pad(img, n=2):
    w, h = img.size
    out = Image.new("RGBA", (w + 2 * n, h + 2 * n), (0, 0, 0, 0))
    out.paste(img, (n, n))
    return out


def outline(img, col=C["out"]):
    src = img.copy().load()
    px = img.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            if src[x, y][3]:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h and src[nx, ny][3]:
                    px[x, y] = col
                    break
    return img


def dith(img, box, col, mode="checker", only_opaque=True):
    px = img.load()
    x0, y0, x1, y1 = box
    for y in range(max(0, y0), min(img.size[1], y1 + 1)):
        for x in range(max(0, x0), min(img.size[0], x1 + 1)):
            if only_opaque and not px[x, y][3]:
                continue
            hit = (
                (x + y) % 2 == 0
                if mode == "checker"
                else (x % 2 == 0 and y % 2 == 0)
                if mode == "sparse"
                else (x % 4 == 0 and y % 4 == (x // 4) % 4)
            )
            if hit:
                px[x, y] = col


def save(img, name, scale):
    w, h = img.size
    img.resize((w * scale, h * scale), Image.NEAREST).save(OUT / name)


# ---------------- items 16x16 ----------------
def item(draw_fn):
    img, d = new(16, 16)
    draw_fn(img, d)
    return outline(pad(img, 1))


def estus(img, d):
    d.rectangle((6, 0, 9, 1), fill=C["c3"])
    d.rectangle((6, 2, 9, 4), fill=C["d5"])
    d.ellipse((2, 4, 13, 15), fill=C["d5"])
    d.ellipse((3, 5, 12, 14), fill=C["e2"])
    d.rectangle((3, 5, 12, 8), fill=C["d4"])
    d.ellipse((4, 9, 11, 14), fill=C["e3"])
    d.point((5, 10), C["e4"])
    d.point((4, 6), C["l2"])


def ember(img, d):
    d.polygon([(8, 0), (13, 7), (12, 13), (8, 15), (4, 13), (3, 7)], fill=C["e2"])
    d.polygon([(8, 4), (11, 8), (10, 12), (8, 13), (6, 12), (5, 8)], fill=C["e3"])
    d.polygon([(8, 8), (9, 11), (8, 12), (7, 11)], fill=C["e4"])


def lens(img, d):
    d.line((10, 10, 15, 15), fill=C["d4"])
    d.line((11, 10, 15, 14), fill=C["d3"])
    d.ellipse((0, 0, 11, 11), fill=C["d5"])
    d.ellipse((2, 2, 9, 9), fill=C["b1"])
    d.point((4, 4), C["b4"])
    d.point((5, 3), C["b3"])


def sign(img, d):
    d.ellipse((1, 1, 14, 14), fill=C["g1"])
    d.ellipse((3, 3, 12, 12), fill=C["d1"])
    d.line((7, 3, 7, 12), fill=C["g3"])
    d.line((3, 7, 12, 7), fill=C["g3"])
    d.point((7, 7), C["l2"])


def ring(img, d):
    d.ellipse((2, 4, 13, 15), fill=C["b2"])
    d.ellipse((4, 6, 11, 13), fill=(0, 0, 0, 0))
    d.arc((2, 4, 13, 15), 200, 280, fill=C["b3"])
    d.rectangle((6, 1, 9, 4), fill=C["g2"])
    d.rectangle((7, 2, 8, 3), fill=C["r3"])


def tome(img, d):
    d.rectangle((2, 1, 13, 14), fill=C["b2"])
    d.rectangle((3, 14, 13, 15), fill=C["l1"])
    d.line((2, 1, 2, 14), fill=C["b1"])
    d.line((13, 2, 13, 14), fill=C["b3"])
    d.rectangle((6, 5, 9, 9), fill=C["g2"])
    d.point((7, 6), C["g3"])


def titanite(img, d):
    d.polygon([(8, 0), (13, 6), (10, 15), (5, 15), (2, 6)], fill=C["b3"])
    d.polygon([(8, 0), (13, 6), (10, 15), (8, 9)], fill=C["b2"])
    d.line((5, 4, 6, 9), fill=C["b4"])
    d.point((7, 2), C["b4"])


def soul(img, d):
    d.ellipse((3, 5, 12, 14), fill=C["b3"])
    d.ellipse((5, 7, 10, 12), fill=C["b4"])
    d.polygon([(7, 0), (9, 3), (10, 6), (5, 6)], fill=C["b3"])
    d.point((7, 9), (255, 255, 255, 255))


def katana_icon(img, d):
    d.line((3, 12, 14, 1), fill=C["l2"])
    d.line((4, 12, 15, 1), fill=C["l1"])
    d.line((2, 10, 6, 14), fill=C["g2"])
    d.line((0, 15, 3, 12), fill=C["c3"])


def hammer_icon(img, d):
    d.line((2, 15, 10, 7), fill=C["d5"])
    d.line((3, 15, 11, 7), fill=C["d4"])
    d.polygon([(8, 1), (12, 0), (15, 4), (13, 8), (9, 9), (6, 5)], fill=C["b2"])
    d.line((8, 1, 12, 0), fill=C["b3"])
    d.point((10, 2), C["b4"])


# ---------------- slash ----------------
def slash():
    img, d = new(40, 40)
    d.line((36, 3, 4, 35), fill=C["e3"], width=4)
    d.line((35, 4, 5, 34), fill=C["l2"], width=2)
    for p in ((37, 2), (3, 36), (38, 1), (2, 37)):
        d.point(p, C["e2"])
    return img


# ---------------- anvil scene ----------------
def anvil_scene():
    img, d = new(48, 30)
    d.rectangle((16, 20, 32, 29), fill=C["d2"])
    dith(img, (16, 20, 32, 29), C["d1"])
    d.polygon(
        [(6, 10), (40, 10), (44, 14), (34, 14), (30, 20), (18, 20), (14, 14), (6, 13)], fill=C["d4"]
    )
    d.line((6, 10, 40, 10), fill=C["d5"])
    dith(img, (14, 14, 34, 20), C["d3"])
    d.line((12, 9, 34, 3), fill=C["d5"])
    d.line((12, 8, 34, 2), fill=C["d4"])
    d.polygon([(32, 0), (40, 0), (41, 7), (33, 8)], fill=C["b2"])
    d.line((32, 0, 40, 0), fill=C["b3"])
    d.point((35, 2), C["b4"])
    for p in ((43, 4), (45, 7), (42, 1), (46, 2), (40, 9)):
        d.point(p, C["e3"])
    d.point((44, 6), C["e4"])
    return outline(pad(img, 2))


# ---------------- emit ----------------
# The knight, the Warden, the bonfire, the Ronin maps, the arena and the home stage are generated
# art run through the ASHEN pipeline: see ronin.py. This script keeps the small UI pieces.
for name, fn in dict(
    estus=estus,
    ember=ember,
    lens=lens,
    sign=sign,
    ring=ring,
    tome=tome,
    titanite=titanite,
    soul=soul,
    katana=katana_icon,
    hammer=hammer_icon,
).items():
    save(item(fn), f"item_{name}.png", 3)
save(slash(), "slash.png", 8)
save(anvil_scene(), "anvil.png", 4)

# contact sheet for review
files = sorted(OUT.glob("*.png"))
print("\n".join(f"{f.name} {Image.open(f).size}" for f in files))
