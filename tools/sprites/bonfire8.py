"""8-frame pixel bonfire for a smooth flicker. Same palette and size as the 3-frame sheet in sprites.py."""

import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(sys.argv[1])


def H(c):
    return tuple(int(c[i : i + 2], 16) for i in (1, 3, 5)) + (255,)


C = {
    k: H(v)
    for k, v in dict(
        out="#0b0a08",
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
    ).items()
}


def outline(img):
    src = img.copy().load()
    px = img.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            if src[x, y][3]:
                continue
            if any(
                0 <= x + dx < w and 0 <= y + dy < h and src[x + dx, y + dy][3]
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
            ):
                px[x, y] = C["out"]
    return img


def frame(i, n=8):
    t = 2 * math.pi * i / n
    img = Image.new("RGBA", (24, 32), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((1, 25, 23, 31), fill=C["d2"])
    for y in range(25, 29):
        for x in range(1, 24):
            if (x + y) % 2 == 0 and img.getpixel((x, y))[3]:
                img.putpixel((x, y), C["d3"])
    d.line((4, 27, 19, 25), fill=C["d4"])
    d.line((5, 25, 18, 28), fill=C["d4"])
    sway = 1.6 * math.sin(t)
    lift = 1.2 * math.cos(2 * t)
    tip = (round(12 + sway), round(10 - lift))
    d.polygon(
        [tip, (round(16.5 + sway * 0.5), 18), (17, 26), (7, 26), (round(7.5 + sway * 0.5), 18)],
        fill=C["e2"],
    )
    tip2 = (round(12 + sway * 0.8), round(15 - lift * 0.8))
    d.polygon(
        [tip2, (round(15 + sway * 0.3), 21), (15, 26), (9, 26), (round(9 + sway * 0.3), 21)],
        fill=C["e3"],
    )
    tip3 = (round(12 + sway * 0.5), round(20 - lift * 0.5))
    d.polygon([tip3, (14, 26), (10, 26)], fill=C["e4"])
    # rising sparks, phase-shifted so they climb across frames
    for k, sx in enumerate((8, 15, 11)):
        y = 9 - ((i * 1.5 + k * 3) % 9)
        x = sx + round(math.sin(t + k))
        if y > 0:
            img.putpixel((x, round(y)), C["e3"] if k % 2 else C["e4"])
    d.line((12, 1, 12, 27), fill=C["l1"])
    d.line((13, 3, 13, 27), fill=C["d5"])
    d.line((9, 6, 15, 6), fill=C["d5"])
    d.point((12, 0), C["l2"])
    for y in range(13, 24, 2):
        d.point((11, y), C["d4"])
        d.point((14, y + 1), C["d4"])
    out = Image.new("RGBA", (28, 36), (0, 0, 0, 0))
    out.paste(img, (2, 2))
    return outline(out)


frames = [frame(i) for i in range(8)]
sheet = Image.new("RGBA", (28 * 8, 36), (0, 0, 0, 0))
for i, f in enumerate(frames):
    sheet.paste(f, (i * 28, 0))
sheet.resize((28 * 8 * 4, 36 * 4), Image.NEAREST).save(OUT / "bonfire_sheet8.png")
print(sheet.size)
