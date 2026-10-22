"""Procedural pixel-art sprites for DontYouDareGoHollow (placeholder art).

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


def glyph(d, rows, ox, oy, col):
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch == "#":
                d.point((ox + x, oy + y), col)


# ---------------- knight, front ----------------
def knight_front():
    img, d = new(36, 48)
    d.polygon([(10, 18), (26, 18), (30, 46), (6, 46)], fill=C["c2"])
    dith(img, (6, 34, 30, 46), C["c1"])
    d.rectangle((13, 36, 16, 44), fill=C["d3"])
    d.rectangle((20, 36, 23, 44), fill=C["d3"])
    d.rectangle((12, 43, 16, 46), fill=C["d2"])
    d.rectangle((20, 43, 24, 46), fill=C["d2"])
    d.polygon([(11, 18), (25, 18), (24, 36), (12, 36)], fill=C["d4"])
    d.line((13, 19, 13, 34), fill=C["d5"])
    dith(img, (19, 24, 24, 36), C["d3"])
    d.rectangle((12, 30, 24, 31), fill=C["d2"])
    d.rectangle((17, 30, 19, 31), fill=C["g2"])
    d.rectangle((8, 22, 11, 33), fill=C["d4"])
    d.rectangle((25, 22, 28, 33), fill=C["d4"])
    d.rectangle((8, 33, 11, 35), fill=C["d3"])
    d.rectangle((25, 33, 28, 35), fill=C["d3"])
    d.ellipse((6, 15, 15, 23), fill=C["d5"])
    d.ellipse((21, 15, 30, 23), fill=C["d5"])
    d.line((8, 16, 12, 16), fill=C["l1"])
    d.line((24, 16, 28, 16), fill=C["l1"])
    d.rectangle((12, 15, 24, 18), fill=C["c3"])
    d.ellipse((13, 3, 23, 12), fill=C["d5"])
    d.rectangle((13, 8, 23, 16), fill=C["d5"])
    d.line((15, 4, 15, 14), fill=C["l1"])
    dith(img, (19, 9, 23, 16), C["d4"])
    d.line((14, 11, 22, 11), fill=C["out"])
    d.point((16, 11), C["e2"])
    d.point((20, 11), C["e2"])
    d.line((18, 0, 18, 3), fill=C["c3"])
    d.point((17, 1), C["c3"])
    # katana (viewer left)
    d.line((9, 33, 1, 3), fill=C["l2"])
    d.line((10, 33, 2, 3), fill=C["l1"])
    d.rectangle((6, 32, 11, 33), fill=C["g2"])
    d.line((10, 35, 11, 40), fill=C["c3"])
    # hammer (viewer right)
    d.line((27, 35, 31, 12), fill=C["d5"])
    d.rectangle((27, 6, 35, 12), fill=C["b2"])
    d.line((27, 6, 35, 6), fill=C["b3"])
    d.point((28, 7), C["b4"])
    img = outline(pad(img, 2))
    return img


# ---------------- knight, back ----------------
def knight_back():
    img, d = new(26, 36)
    d.polygon([(6, 11), (20, 11), (24, 34), (2, 34)], fill=C["c2"])
    dith(img, (2, 24, 24, 34), C["c1"])
    d.line((12, 13, 11, 33), fill=C["c1"])
    d.rectangle((7, 32, 10, 35), fill=C["d2"])
    d.rectangle((15, 32, 18, 35), fill=C["d2"])
    d.ellipse((2, 8, 10, 15), fill=C["d5"])
    d.ellipse((16, 8, 24, 15), fill=C["d5"])
    d.line((4, 9, 8, 9), fill=C["l1"])
    d.line((18, 9, 22, 9), fill=C["l1"])
    d.ellipse((8, 1, 18, 12), fill=C["d5"])
    dith(img, (8, 7, 18, 12), C["d4"])
    d.line((10, 2, 14, 2), fill=C["l1"])
    d.rectangle((9, 11, 17, 13), fill=C["c3"])
    d.line((21, 26, 25, 2), fill=C["l2"])
    d.line((22, 26, 25, 7), fill=C["l1"])
    d.rectangle((19, 25, 24, 26), fill=C["g2"])
    img = outline(pad(img, 2))
    return img


# ---------------- warden ----------------
TE = [
    "...........",
    ".#########.",
    ".#########.",
    "......##...",
    ".....##....",
    "....##.....",
    "....##.....",
    "....##.....",
    "....###....",
    ".....#####.",
    "......####.",
]


def warden_body():
    img, d = new(64, 80)
    d.polygon([(14, 30), (50, 30), (57, 79), (7, 79)], fill=C["d2"])
    dith(img, (34, 34, 57, 79), C["d1"])
    for x in range(7, 58, 3):
        d.line((x, 77, x, 79), fill=C["d1"])
    d.polygon([(18, 27), (46, 27), (44, 50), (20, 50)], fill=C["d3"])
    d.line((21, 29, 21, 48), fill=C["d4"])
    d.line((32, 28, 32, 49), fill=C["d2"])
    dith(img, (34, 30, 44, 50), C["d2"])
    d.rectangle((20, 44, 44, 46), fill=C["d1"])
    d.rectangle((30, 44, 34, 46), fill=C["g1"])
    d.ellipse((7, 21, 25, 37), fill=C["d4"])
    d.ellipse((39, 21, 57, 37), fill=C["d4"])
    d.line((10, 22, 20, 22), fill=C["d5"])
    d.line((43, 22, 53, 22), fill=C["d5"])
    dith(img, (7, 30, 25, 37), C["d3"])
    dith(img, (39, 30, 57, 37), C["d3"])
    for p in ((12, 26), (20, 26), (44, 26), (52, 26)):
        d.point(p, C["g2"])
    d.ellipse((21, 1, 43, 16), fill=C["d3"])
    d.polygon([(21, 8), (43, 8), (47, 28), (17, 28)], fill=C["d3"])
    d.line((24, 3, 24, 22), fill=C["d4"])
    dith(img, (36, 8, 47, 28), C["d2"])
    d.polygon([(26, 11), (38, 11), (40, 26), (24, 26)], fill=C["out"])
    d.rectangle((28, 17, 29, 18), fill=C["r3"])
    d.rectangle((35, 17, 36, 18), fill=C["r3"])
    for p in ((27, 17), (30, 17), (34, 17), (37, 17), (28, 16), (36, 16)):
        d.point(p, C["r1"])
    d.rectangle((48, 33, 54, 48), fill=C["d3"])
    dith(img, (48, 33, 54, 48), C["d2"])
    d.rectangle((47, 46, 56, 53), fill=C["d4"])
    d.line((47, 46, 56, 46), fill=C["d5"])
    # shield
    d.ellipse((1, 38, 31, 70), fill=C["d4"])
    d.ellipse((4, 41, 28, 67), fill=C["d3"])
    dith(img, (16, 54, 31, 70), C["d2"])
    d.arc((1, 38, 31, 70), 200, 300, fill=C["d5"])
    for p in ((16, 39), (16, 69), (2, 54), (30, 54)):
        d.point(p, C["g2"])
    glyph(d, TE, 11, 48, C["e3"])
    glyph(d, [r.replace("#", "#") for r in TE[1:3]], 11, 49, C["e3"])
    img = outline(pad(img, 2))
    return img


def warden_weapon():
    img, d = new(26, 82)
    d.rectangle((12, 10, 13, 81), fill=C["d4"])
    d.line((12, 10, 12, 81), fill=C["d5"])
    for y in range(40, 60, 3):
        d.line((11, y, 14, y), fill=C["c2"])
    d.polygon([(2, 0), (24, 0), (24, 16), (2, 16)], fill=C["d4"])
    d.line((2, 0, 24, 0), fill=C["l1"])
    d.line((2, 1, 24, 1), fill=C["d5"])
    dith(img, (2, 8, 24, 16), C["d3"])
    d.rectangle((2, 0, 3, 16), fill=C["g1"])
    d.rectangle((23, 0, 24, 16), fill=C["g1"])
    d.rectangle((10, 17, 15, 19), fill=C["d3"])
    img = outline(pad(img, 2))
    return img


# ---------------- bonfire (3 frames) ----------------
def bonfire_frame(i):
    img, d = new(24, 32)
    d.ellipse((1, 25, 23, 31), fill=C["d2"])
    dith(img, (1, 25, 23, 28), C["d3"])
    d.line((4, 27, 19, 25), fill=C["d4"])
    d.line((5, 25, 18, 28), fill=C["d4"])
    flames = [
        [(12, 10), (16, 18), (17, 26), (7, 26), (8, 18)],
        [(11, 9), (17, 17), (17, 26), (7, 26), (7, 19)],
        [(13, 11), (17, 19), (16, 26), (7, 26), (9, 17)],
    ]
    mids = [
        [(12, 15), (15, 21), (14, 26), (10, 26), (9, 21)],
        [(11, 14), (15, 20), (15, 26), (10, 26), (9, 22)],
        [(13, 16), (15, 22), (14, 26), (10, 26), (10, 20)],
    ]
    cores = [
        [(12, 20), (14, 26), (10, 26)],
        [(11, 19), (13, 26), (10, 26)],
        [(13, 21), (14, 26), (11, 26)],
    ]
    d.polygon(flames[i], fill=C["e2"])
    d.polygon(mids[i], fill=C["e3"])
    d.polygon(cores[i], fill=C["e4"])
    sparks = [[(9, 7), (15, 4)], [(14, 6), (8, 3)], [(10, 5), (16, 8)]][i]
    for p in sparks:
        d.point(p, C["e3"])
    d.line((12, 1, 12, 27), fill=C["l1"])
    d.line((13, 3, 13, 27), fill=C["d5"])
    d.line((9, 6, 15, 6), fill=C["d5"])
    d.point((12, 0), C["l2"])
    for y in range(13, 24, 2):
        d.point((11, y), C["d4"])
        d.point((14, y + 1), C["d4"])
    img = outline(pad(img, 2))
    return img


def bonfire_sheet():
    frames = [bonfire_frame(i) for i in range(3)]
    w, h = frames[0].size
    sheet = Image.new("RGBA", (w * 3, h), (0, 0, 0, 0))
    for i, f in enumerate(frames):
        sheet.paste(f, (i * w, 0))
    return sheet


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


# ---------------- landscapes ----------------
def sky_bands(img, d, w, h, bands):
    y = 0
    for col, hh in bands:
        d.rectangle((0, y, w, y + hh), fill=col)
        y += hh
    # dithered seams
    y = 0
    for i, (col, hh) in enumerate(bands[:-1]):
        y += hh
        nxt = bands[i + 1][0]
        for yy in range(y - 2, y + 2):
            for x in range(w):
                if (x + yy) % 2 == 0:
                    img.putpixel((x, yy), nxt if yy < y else col)


def world_map():
    W, Hh = 260, 225
    img, d = new(W, Hh, C["s1"])
    sky_bands(img, d, W, Hh, [(C["s1"], 30), (C["s2"], 30), (C["s3"], 40), (C["s2"], 125)])
    # dark sun
    d.ellipse((165, 12, 189, 36), fill=C["g2"])
    d.ellipse((167, 14, 187, 34), fill=C["out"])
    for x in range(158, 197):
        for y in range(5, 44):
            if (
                ((x - 177) ** 2 + (y - 24) ** 2) in range(170, 260)
                and (x + y) % 2 == 0
                and img.getpixel((x, y)) != C["g2"]
            ):
                img.putpixel((x, y), C["g1"])
    d.polygon(
        [
            (0, 90),
            (30, 62),
            (52, 78),
            (82, 45),
            (112, 75),
            (140, 52),
            (175, 70),
            (205, 38),
            (232, 58),
            (260, 42),
            (260, 225),
            (0, 225),
        ],
        fill=C["s4"],
    )
    d.polygon(
        [
            (0, 117),
            (35, 95),
            (65, 107),
            (100, 85),
            (130, 100),
            (160, 82),
            (190, 95),
            (220, 65),
            (260, 82),
            (260, 225),
            (0, 225),
        ],
        fill=C["s5"],
    )
    dith(img, (0, 82, 260, 120), C["s4"], only_opaque=False)
    # kiln glow + peak
    for x in range(195, 256):
        for y in range(15, 70):
            r = (x - 225) ** 2 + (y - 37) ** 2
            if r < 260 and (x % 2 == 0 and y % 2 == 0):
                img.putpixel((x, y), C["e1"])
            if r < 70 and (x + y) % 2 == 0:
                img.putpixel((x, y), C["e1"])
    d.polygon([(217, 44), (225, 26), (233, 44)], fill=C["d3"])
    d.point((225, 27), C["e3"])
    d.point((224, 29), C["e4"])
    d.line((225, 28, 225, 24), fill=C["e3"])
    # golden city
    for x, h, w in ((180, 18, 4), (186, 26, 5), (193, 14, 4), (198, 20, 4)):
        d.rectangle((x, 82 - h, x + w, 82), fill=C["d3"])
        d.point((x + w // 2, 82 - h - 1), C["g3"])
        d.line((x, 82 - h, x + w, 82 - h), fill=C["g2"])
    d.rectangle((178, 82, 204, 85), fill=C["d3"])
    d.polygon(
        [
            (0, 150),
            (45, 130),
            (82, 140),
            (117, 125),
            (155, 135),
            (195, 118),
            (260, 130),
            (260, 225),
            (0, 225),
        ],
        fill=H("#2e261e"),
    )
    dith(img, (0, 118, 260, 140), C["s5"], mode="sparse", only_opaque=False)
    # fortress
    d.rectangle((130, 110, 150, 125), fill=C["d2"])
    for x in range(130, 151, 4):
        d.rectangle((x, 107, x + 1, 109), fill=C["d2"])
    d.rectangle((143, 100, 149, 110), fill=C["d2"])
    d.rectangle((144, 97, 145, 99), fill=C["d2"])
    d.rectangle((138, 118, 141, 125), fill=C["out"])
    d.point((146, 104), C["e2"])
    # catacombs
    d.ellipse((67, 109, 83, 121), fill=C["d2"])
    d.rectangle((67, 115, 83, 122), fill=C["d2"])
    d.ellipse((72, 113, 78, 119), fill=C["out"])
    d.rectangle((72, 116, 78, 122), fill=C["out"])
    for p in ((69, 112), (81, 112), (75, 109)):
        d.point(p, C["d5"])
    d.polygon(
        [(0, 185), (55, 170), (105, 177), (160, 165), (215, 175), (260, 168), (260, 225), (0, 225)],
        fill=C["s2"],
    )
    dith(img, (0, 165, 260, 180), H("#2e261e"), mode="sparse", only_opaque=False)
    # village
    for x, y in ((90, 155), (98, 157), (105, 154)):
        d.rectangle((x, y, x + 6, y + 5), fill=C["d3"])
        d.polygon([(x - 1, y), (x + 3, y - 4), (x + 7, y)], fill=C["d4"])
        d.point((x + 3, y + 3), C["e2"])
    # dead trees
    for x, y in ((20, 172), (120, 160), (170, 128), (240, 170), (60, 140)):
        d.line((x, y, x, y - 9), fill=C["d1"])
        d.line((x, y - 6, x - 3, y - 9), fill=C["d1"])
        d.line((x, y - 4, x + 3, y - 8), fill=C["d1"])
    # shrine ruin
    d.rectangle((36, 165, 42, 176), fill=C["d3"])
    d.polygon([(35, 165), (39, 160), (43, 165)], fill=C["d3"])
    d.rectangle((60, 168, 64, 176), fill=C["d3"])
    for x in range(30, 75):
        for y in range(155, 195):
            r = (x - 52) ** 2 + (y - 175) ** 2
            if (
                (r < 70 and (x + y) % 2 == 0) or (r < 180 and x % 2 == 0 and y % 2 == 0)
            ) and img.getpixel((x, y))[:3] in (C["s2"][:3], H("#2e261e")[:3]):
                img.putpixel((x, y), C["e1"])
    # path dots
    pts = [(52, 175), (97, 152), (75, 117), (140, 120), (190, 80), (225, 37)]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        steps = max(abs(x1 - x0), abs(y1 - y0))
        for i in range(0, steps, 4):
            x = round(x0 + (x1 - x0) * i / steps)
            y = round(y0 + (y1 - y0) * i / steps)
            img.putpixel((x, y), C["g1"])
    # fog
    for x in range(110, 260):
        for y in range(25, 135):
            if (x % 3 == 0 and y % 3 == (x // 3) % 3) and (
                (x - 200) ** 2 / 4 + (y - 80) ** 2
            ) < 2600:
                img.putpixel((x, y), H("#5a564e"))
    # vignette
    for x in range(W):
        for y in range(Hh):
            edge = min(x, y, W - 1 - x, Hh - 1 - y)
            if edge < 4 or (edge < 8 and (x + y) % 2 == 0):
                img.putpixel((x, y), C["out"])
    return img


def arena():
    W, Hh = 360, 225
    img, d = new(W, Hh, C["s1"])
    # back wall bricks
    d.rectangle((0, 0, W, 150), fill=C["s3"])
    for row, y in enumerate(range(0, 150, 6)):
        off = 0 if row % 2 == 0 else 6
        d.line((0, y, W, y), fill=C["s1"])
        for x in range(off, W, 12):
            d.line((x, y, x, y + 5), fill=C["s1"])
    dith(img, (0, 0, W, 60), C["s2"], only_opaque=False)
    dith(img, (0, 0, W, 20), C["s1"], mode="sparse", only_opaque=False)
    # arch
    d.rectangle((70, 40, 190, 150), fill=C["s1"])
    d.ellipse((70, 10, 190, 80), fill=C["s1"])
    d.arc((66, 6, 194, 84), 180, 360, fill=C["d4"], width=4)
    d.rectangle((66, 45, 69, 150), fill=C["d4"])
    d.rectangle((191, 45, 194, 150), fill=C["d4"])
    dith(img, (70, 20, 190, 150), C["s2"], mode="sparse", only_opaque=False)
    # pillars
    for x0 in (16, 222):
        d.rectangle((x0, 28, x0 + 18, 170), fill=C["d2"])
        d.rectangle((x0 - 3, 24, x0 + 21, 30), fill=C["d3"])
        d.line((x0 + 2, 30, x0 + 2, 168), fill=C["d3"])
        dith(img, (x0 + 10, 30, x0 + 18, 170), C["d1"], only_opaque=False)
        d.rectangle((x0 + 7, 60, x0 + 11, 64), fill=C["d4"])
        d.polygon([(x0 + 9, 50), (x0 + 12, 57), (x0 + 6, 57)], fill=C["e2"])
        d.point((x0 + 9, 54), C["e4"])
        d.point((x0 + 9, 53), C["e3"])
        for x in range(x0 - 10, x0 + 30):
            for y in range(40, 75):
                if (
                    ((x - x0 - 9) ** 2 + (y - 55) ** 2) < 180
                    and (x + y) % 2 == 0
                    and img.getpixel((x, y))[:3] == C["s3"][:3]
                ):
                    img.putpixel((x, y), C["e1"])
    # floor
    d.rectangle((0, 150, W, Hh), fill=C["s2"])
    for y in (156, 166, 180, 198, 220):
        d.line((0, y, W, y), fill=C["s1"])
    vx = 140
    for x in range(-400, 800, 50):
        d.line((vx, 150, x, Hh), fill=C["s1"])
    dith(img, (0, 150, W, 158), C["s3"], only_opaque=False)
    for x in range(0, W):
        for y in range(152, 176):
            if (x % 3 == 0 and y % 3 == (x // 3) % 3) and (
                (x - 140) ** 2 / 9 + (y - 162) ** 2 * 4
            ) < 2400:
                img.putpixel((x, y), H("#4a463f"))
    for x in range(W):
        for y in range(Hh):
            edge = min(x, y, W - 1 - x, Hh - 1 - y)
            if edge < 4 or (edge < 10 and (x + y) % 2 == 0):
                img.putpixel((x, y), C["out"])
    return img


# ---------------- emit ----------------
# The hero is hand-made art now (tools/sprites/art/knight_front_64.png, 32x60 from the
# 64 px export of the ASHEN pipeline), drawn at 3x to match the 3-4 px grain of the scenes.
save(Image.open(Path(__file__).parent / "art" / "knight_front_64.png").convert("RGBA"),
     "knight_front.png", 3)
save(knight_back(), "knight_back.png", 5)
wb = warden_body()
ww = warden_weapon()
save(wb, "warden_body.png", 6)
save(ww, "warden_weapon.png", 6)
comp = Image.new("RGBA", (wb.size[0] + 10, wb.size[1]), (0, 0, 0, 0))
comp.paste(wb, (0, 0))
comp.alpha_composite(ww, (39, 2))
save(comp, "warden_small.png", 2)
save(bonfire_sheet(), "bonfire_sheet.png", 4)
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
wm = world_map()
save(wm, "map_bg.png", 4)
save(wm.crop((20, 130, 107, 170)), "map_banner.png", 4)
save(arena(), "arena_bg.png", 4)

# contact sheet for review
files = sorted(OUT.glob("*.png"))
print("\n".join(f"{f.name} {Image.open(f).size}" for f in files))
