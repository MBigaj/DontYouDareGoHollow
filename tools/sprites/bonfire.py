"""The bonfire: a broken greatsword in a ring of stones and ash, and a looping 8-frame flame.

The base (stones, ash, bones, the sword's silhouette) is the generated source art run through
the ASHEN pipeline at 72x90 (ronin.py does that and calls sheet()). This module repaints the
sword crisply, then animates the fire over it: a looping noise flame, embers breathing in the
ash and climbing sparks. Each frame is 72x90; ronin.py scales the sheet 2x to 1152x180.
"""

import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from kit import LEATHER, Canvas, hx, ramp  # noqa: E402

N = 8
W, H = 72, 90
CX = 35  # the blade's centre column
GROUND = 59  # where the blade enters the ash
FIRE = ramp("5a1410", "9a2a16", "d0501c", "f08024", "f8ae3c", "fcd878", "fff6dc")
CUT = (0.02, 0.16, 0.32, 0.48, 0.64, 0.8, 0.96)
STEEL = ramp("120f12", "211c1e", "322b2c", "463d3c", "5e5450", "7a6e66", "a09284", "c8baa8")
GOLD = ramp("2e1e0c", "5a3e18", "8a6428", "b88c3c", "e0b45a", "f6d98a")
SPARK = (hx("fff6dc"), hx("fce08a"), hx("f08a2a"))


def sword() -> Canvas:
    """The greatsword, crisp: notched blade, gold crossguard and pommel, wrapped grip."""
    c = Canvas(W, H)
    blade = c.poly([(CX - 2.5, 23), (CX + 2.5, 23), (CX + 2.5, GROUND), (CX - 2.5, GROUND)])
    # the break: chips out of the right edge, low on the blade
    for y0, depth in ((30, 1), (37, 2), (44, 1), (49, 2)):
        blade &= ~c.poly([(CX + 3, y0), (CX + 3 - depth, y0 + 1.5), (CX + 3, y0 + 3)])
    c.shade(blade, STEEL, light=(-1, -0.3), soft=0.7, lo=0.2, hi=0.95, relief=4)
    c.fill(c.rect((CX, 25, CX, GROUND)) & blade, STEEL[2])  # fuller
    c.fill(c.rect((CX - 2, 24, CX - 2, GROUND)) & blade, STEEL[6])  # lit edge
    c.noise_speckle(blade & (c.xx > CX - 2), hx("5a3420"), 0.12, seed=3)  # rust
    # crossguard with down-swept tips and a boss
    guard = c.poly([(CX - 9, 20), (CX + 9, 20), (CX + 10, 23), (CX + 7, 22), (CX - 7, 22), (CX - 10, 23)])
    c.shade(guard, GOLD, light=(-0.7, -0.7), soft=0.6, lo=0.15, hi=1.0, relief=3)
    boss = c.ellipse((CX - 2, 19, CX + 2, 24))
    c.shade(boss, GOLD, light=(-0.7, -0.7), soft=0.5, lo=0.25, hi=1.0)
    c.dot(CX, 21, hx("c44a3a"))
    # grip wrapped in old leather, a loose strap hanging
    grip = c.rect((CX - 1, 8, CX + 1, 19))
    c.fill(grip, LEATHER[1])
    for y in range(9, 19, 2):
        c.fill(c.rect((CX - 1, y, CX + 1, y)), LEATHER[3])
    c.dot(CX - 1, 9, LEATHER[4])
    c.fill(c.line([(CX + 2, 10), (CX + 3, 13), (CX + 3, 16)]), LEATHER[2])
    # pommel
    pommel = c.ellipse((CX - 2.5, 2, CX + 2.5, 7.5))
    c.shade(pommel, GOLD, light=(-0.7, -0.7), soft=0.5, lo=0.2, hi=1.0)
    c.dot(CX, 4, GOLD[5])
    c.outline(darken=0.25)
    return c


# the tongues: (offset from the blade at the base, height, width, curl, phase)
TONGUES = ((-5.0, 40, 7.0, 6.0, 0.0), (5.5, 36, 7.0, -6.0, 2.1), (-1.0, 48, 5.5, 4.5, 4.0),
           (2.0, 26, 11.0, -2.0, 5.2), (-10.0, 20, 6.5, 2.0, 1.3), (10.5, 18, 6.5, -2.0, 3.3))  # fmt: skip


def flame_field(c: Canvas, t: float) -> tuple[np.ndarray, np.ndarray]:
    """Curling tongues that spiral up the blade, each breathing on its own phase.

    Returns the whole field and the part of it that passes in front of the blade."""
    x, y = c.xx.astype(float), c.yy.astype(float)
    field = np.full_like(x, -1.0)
    front = np.full_like(x, -1.0)
    for ox, ht, wd, curl, ph in TONGUES:
        breath = 1 + 0.12 * math.sin(t + ph) + 0.06 * math.sin(2 * t + ph * 1.7)
        u = np.clip((GROUND + 1 - y) / (ht * breath), 0, 1.2)  # 0 at the ash, 1 at the tip
        turn = u * 4.2 + t + ph
        cx = CX + ox * np.clip(1 - u, 0, 1) ** 1.5 + curl * np.sin(turn) * np.sqrt(u)
        w = wd * np.clip(1 - u, 0, 1) ** 0.55 * (0.82 + 0.18 * np.cos(u * 6 + t * 2 + ph))
        tongue = 1 - np.abs(x - cx) / np.maximum(w, 0.01) - 0.3 * u**2
        field = np.maximum(field, tongue)
        front = np.maximum(front, np.where(np.cos(turn) > 0.2, tongue, -1.0))
    lick = np.sin(0.9 * y + 2 * t + 0.7 * x) + 0.6 * np.sin(0.55 * y - 3 * t - 0.9 * x)
    field = np.where(field > -0.15, field + 0.14 * lick, field)
    front = np.where(front > -0.15, front + 0.14 * lick, front)
    core = 1 - np.hypot((x - CX) / 7.0, (y - GROUND + 3) / 9.5)  # the white-hot heart
    field = np.maximum(field, core * 1.25)
    keep = (y <= GROUND + 2) & (y >= 3)
    return np.where(keep, field, -1.0), np.where(keep, front, -1.0)


def wisps(c: Canvas, t: float) -> np.ndarray:
    """Scraps of flame that tear off the tips and rise, shrinking, on a loop."""
    x, y = c.xx.astype(float), c.yy.astype(float)
    field = np.full_like(x, -1.0)
    for k, (sx, ph) in enumerate(((CX - 5, 0.0), (CX + 4, 0.37), (CX - 1, 0.71), (CX + 7, 0.55))):
        rise = ((t / (2 * math.pi)) + ph) % 1.0
        wy = GROUND - 36 - rise * 22
        wx = sx + 3 * math.sin(rise * 5 + k)
        r = 3.2 * (1 - rise) + 0.6
        field = np.maximum(field, 0.9 * (1 - np.hypot((x - wx) / r, (y - wy) / (r * 1.7))))
    return field


def firelight(c: Canvas, t: float, i: int) -> None:
    """Warm light from the flame across the ash and stones, flickering frame to frame."""
    from kit import BAYER4

    flick = 0.82 + 0.12 * math.sin(t * 2 + 0.7) + 0.06 * math.sin(t * 3 + 2.1)
    d = np.hypot((c.xx - CX) / 1.35, (c.yy - GROUND + 2) * 1.1)
    k = np.clip(1 - d / 38, 0, 1) ** 1.1 * flick
    q = np.floor(k * 4 + BAYER4[c.yy % 4, (c.xx + i) % 4] * 0.999) / 4
    m = (q > 0) & c.opaque()
    warm = np.array(FIRE[4], float)
    base = c.a[..., :3].astype(float)
    lum = base @ np.array([0.3, 0.59, 0.11]) / 255
    out = base + (warm * (0.4 + lum[..., None]) - base) * q[..., None] * 0.7
    c.a[m, :3] = out[m].round().clip(0, 255).astype(np.uint8)


def paint_fire(c: Canvas, f: np.ndarray, mask: np.ndarray) -> None:
    lvl = np.full(f.shape, -1)
    for k, cut in enumerate(CUT):
        lvl[f > cut] = k
    m = (lvl >= 0) & mask
    c.a[m, :3] = np.array(FIRE)[lvl[m]]
    c.a[m, 3] = 255


def frame(base: Canvas, blade: Canvas, i: int) -> Canvas:
    t = 2 * math.pi * i / N
    c = Canvas(W, H)
    c.a = base.a.copy()
    # clear the pipeline's sword above the ash; the crisp one replaces it
    above = (c.yy < GROUND - 1) & (np.abs(c.xx - CX) <= 11)
    c.a[above] = 0

    # embers in the ash breathe: hot pixels brighten and dim in waves
    rgb = c.a[..., :3].astype(int)
    hot = (rgb[..., 0] > 150) & (rgb[..., 0] - rgb[..., 2] > 90) & c.opaque()
    wave = np.sin(c.xx * 0.9 + c.yy * 1.3 - t * 2) + 0.6 * np.sin(c.xx * 2.1 - t * 3)
    c.a[hot & (wave > 0.9), :3] = np.array(FIRE[5])
    c.a[hot & (wave < -0.9), :3] = np.array(FIRE[2])
    near = np.hypot((c.xx - CX) / 1.6, c.yy - GROUND) < 9
    c.a[hot & near & (wave > 0.2), :3] = np.array(FIRE[6])

    firelight(c, t, i)
    f, fr = flame_field(c, t)
    f = np.maximum(f, wisps(c, t))
    paint_fire(c, f, np.ones_like(c.opaque()))  # the fire behind the blade
    c.paste(blade, 0, 0)
    # the blade lit from below, its edge catching the fire
    bm = blade.opaque() & (c.yy > GROUND - 22) & (c.yy < GROUND)
    k = np.clip((c.yy - (GROUND - 22)) / 22.0, 0, 1)
    warm = np.array(FIRE[4], float)
    lit = c.a[..., :3].astype(float) * (1 - 0.3 * k[..., None]) + warm * 0.3 * k[..., None]
    c.a[bm, :3] = lit[bm].round().astype(np.uint8)
    # tongues in front of the blade's root
    paint_fire(c, fr, fr > 0.28)  # the turns of the spiral that pass in front
    base_front = c.yy > GROUND - 10 + 2 * np.sin(c.xx * 0.8 + t * 2)
    paint_fire(c, np.where(f > 0.45, f, -1), base_front)

    # sparks climbing on a loop, each on its own phase
    for k_, (sx, ph, amp) in enumerate(((CX - 6, 0, 2), (CX + 5, 3, 3), (CX - 2, 5.5, 2),
                                        (CX + 8, 1.5, 2), (CX - 9, 6.5, 3), (CX + 2, 2.5, 1))):  # fmt: skip
        rise = ((i + ph) % N) / N
        y = int(GROUND - 26 - rise * 26)
        x = int(round(sx + amp * math.sin(t + k_ * 1.7)))
        if 0 <= y < H and 0 <= x < W and not blade.opaque()[y, x]:
            c.dot(x, y, SPARK[0] if rise < 0.3 else SPARK[1] if rise < 0.7 else SPARK[2])
    return c


def unlit(base_img: Image.Image) -> Image.Image:
    """The cold bonfire: no flame, the embers gone to grey ash, the blade unlit."""
    c = Canvas(W, H)
    c.a = np.array(base_img.convert("RGBA"))
    c.a[(c.yy < GROUND - 1) & (np.abs(c.xx - CX) <= 11)] = 0
    rgb = c.a[..., :3].astype(float)
    lum = rgb @ np.array([0.3, 0.59, 0.11])
    hot = (rgb[..., 0] - rgb[..., 2] > 60) & c.opaque()
    cold = np.clip(lum * 0.55, 0, 255)[..., None] * np.array([1.0, 0.97, 1.02])
    c.a[hot, :3] = cold[hot].round().clip(0, 255).astype(np.uint8)
    c.paste(sword(), 0, 0)
    return c.img()


def sheet(base_img: Image.Image) -> Image.Image:
    """All N frames side by side, at native size."""
    base = Canvas(W, H)
    base.a = np.array(base_img.convert("RGBA"))
    blade = sword()
    out = Canvas(W * N, H)
    for i in range(N):
        out.paste(frame(base, blade, i), i * W, 0)
    return out.img()
