"""Shared helpers for the 2x-density sprites (ASHEN art direction).

Numpy canvases, colour ramps from palettes/ashen.hex, volumetric shading of masks,
ordered dithering, selective outlines and rim light. Pure drawing code: no I/O except save().
"""

from __future__ import annotations

import math
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

BAYER4 = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]], float) / 16.0


def hx(s: str) -> np.ndarray:
    s = s.lstrip("#")
    return np.array([int(s[i : i + 2], 16) for i in (0, 2, 4)], np.uint8)


def ramp(*hexes: str) -> list[np.ndarray]:
    return [hx(h) for h in hexes]


# ASHEN master palette ramps (dark to light), see palettes/ashen.hex in the pixel pipeline
VOID = ramp("0a080c", "16131a", "221e28", "302b36", "433d4a", "5c5563", "7d7684", "a49daa")
STEEL = ramp("1b2230", "2b3646", "3e4c5e", "566a7e", "7a8fa3", "a9bccb")
BLOOD = ramp("2a0a0e", "4a1016", "701c20", "9a2c2a", "c44a3a", "e8806a")
EMBER = ramp("5a240c", "8e3e12", "c46a1c", "ec9a2e", "f6c55a")
GOLD = ramp("3a2a14", "7a5a24", "b88c3c", "e0b45a", "f6d98a")
LEATHER = ramp("1c120e", "2e1e18", "4a3226", "6a4a34", "8e6a4a", "b49270")
BONE = ramp("5a4038", "8c6658", "b88e76", "d6b49a", "e8d8c4", "ece6dc")
MOSS = ramp("141c12", "1e2a1c", "34462c", "52683e", "7e9460")
ASH = ramp("120f12", "1d1a1e", "2a2629", "3a3436", "524a49", "6e6560", "8f857b", "b3a898")
IRON = ramp("0e0d10", "1a1a1f", "2a2b31", "3d3f46", "575a62", "7c7f86", "a7a9ac", "d4d2cc")
FOG = ramp("3e3a40", "6a6670", "9c98a0", "cfccd2", "f2f0f2")
OUT = hx("0a080c")


def blend(c1: np.ndarray, c2: np.ndarray, t: float) -> np.ndarray:
    return (c1 * (1 - t) + c2 * t).round().astype(np.uint8)


class Canvas:
    def __init__(self, w: int, h: int, bg: np.ndarray | None = None) -> None:
        self.w, self.h = w, h
        self.a = np.zeros((h, w, 4), np.uint8)
        if bg is not None:
            self.a[..., :3] = bg
            self.a[..., 3] = 255
        self.yy, self.xx = np.mgrid[0:h, 0:w]

    # ---------------- masks
    def _mask(self, fn) -> np.ndarray:  # type: ignore[no-untyped-def]
        im = Image.new("L", (self.w, self.h), 0)
        fn(ImageDraw.Draw(im))
        return np.array(im) > 127

    def poly(self, pts) -> np.ndarray:  # type: ignore[no-untyped-def]
        return self._mask(lambda d: d.polygon([tuple(map(float, p)) for p in pts], fill=255))

    def ellipse(self, box) -> np.ndarray:  # type: ignore[no-untyped-def]
        return self._mask(lambda d: d.ellipse(box, fill=255))

    def rect(self, box) -> np.ndarray:  # type: ignore[no-untyped-def]
        return self._mask(lambda d: d.rectangle(box, fill=255))

    def line(self, pts, width: int = 1) -> np.ndarray:  # type: ignore[no-untyped-def]
        return self._mask(lambda d: d.line([tuple(p) for p in pts], fill=255, width=width))

    def opaque(self) -> np.ndarray:
        return self.a[..., 3] > 0

    # ---------------- painting
    def fill(self, mask: np.ndarray, col: np.ndarray) -> None:
        self.a[mask, :3] = col
        self.a[mask, 3] = 255

    def dot(self, x: int, y: int, col: np.ndarray) -> None:
        if 0 <= x < self.w and 0 <= y < self.h:
            self.a[y, x, :3] = col
            self.a[y, x, 3] = 255

    def get(self, x: int, y: int) -> np.ndarray:
        return self.a[y, x, :3]

    def levels(self, mask: np.ndarray, val: np.ndarray, rmp: list[np.ndarray], dither: float = 0.5) -> None:
        """Paint mask with ramp[level], level from val in 0..1 with ordered dither at band edges."""
        n = len(rmp)
        t = BAYER4[self.yy % 4, self.xx % 4] - 0.5
        idx = np.clip(np.floor(val * (n - 1) + 0.5 + t * dither), 0, n - 1).astype(int)
        pal = np.array(rmp)
        self.a[mask, :3] = pal[idx[mask]]
        self.a[mask, 3] = 255

    def vgrad(self, mask: np.ndarray, rmp: list[np.ndarray], y0: float, y1: float, dither: float = 0.9) -> None:
        val = np.clip((self.yy - y0) / max(y1 - y0, 1), 0, 1)
        self.levels(mask, val, rmp, dither)

    def shade(
        self,
        mask: np.ndarray,
        rmp: list[np.ndarray],
        light: tuple[float, float] = (-0.55, -0.8),
        soft: float = 3.0,
        lo: float = 0.12,
        hi: float = 1.0,
        bias: float = 0.0,
        dither: float = 0.35,
        relief: float = 2.2,
    ) -> None:
        """Volumetric shading: a height field from the blurred mask, lit from `light`."""
        hgt = blur(mask.astype(float), soft)
        gy, gx = np.gradient(hgt)
        nx, ny, nz = -gx * relief, -gy * relief, np.ones_like(hgt) * 0.35
        nl = np.sqrt(nx * nx + ny * ny + nz * nz)
        lx, ly = light
        lz = 0.55
        ll = math.sqrt(lx * lx + ly * ly + lz * lz)
        lam = np.clip((nx * lx + ny * ly + nz * lz) / (nl * ll), 0, 1)
        val = np.clip(lo + (hi - lo) * lam + bias, 0, 1)
        self.levels(mask, val, rmp, dither)

    def noise_speckle(self, mask: np.ndarray, col: np.ndarray, p: float, seed: int = 0) -> None:
        rng = np.random.default_rng(seed)
        m = mask & (rng.random(mask.shape) < p)
        self.fill(m, col)

    def rim(self, mask: np.ndarray, col: np.ndarray, d: tuple[int, int] = (-1, -1), only: np.ndarray | None = None) -> None:
        """Light the mask pixels whose neighbour toward the light is outside the mask."""
        dx, dy = d  # direction toward the light: (-1, 0) lights the left edge, (0, -1) the top
        hit = np.zeros_like(mask)
        if dx:
            hit |= mask & ~shift(mask, -dx, 0)
        if dy:
            hit |= mask & ~shift(mask, 0, -dy)
        if only is not None:
            hit &= only
        self.fill(hit, col)

    def outline(self, darken: float = 0.3, solid: np.ndarray | None = None) -> None:
        """1px selective outline: a much darker version of the neighbouring colour."""
        m = self.opaque()
        ring = np.zeros_like(m)
        nb = np.zeros((self.h, self.w, 3), float)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            sm = shift(m, dx, dy)
            sc = shift3(self.a[..., :3], dx, dy)
            new = sm & ~m & ~ring
            nb[new] = sc[new]
            ring |= new
        if solid is not None:
            self.fill(ring, solid)
            return
        col = (nb * darken + OUT.astype(float) * (1 - darken)).round().astype(np.uint8)
        self.a[ring, :3] = col[ring]
        self.a[ring, 3] = 255

    def inner_lines(self, darken: float = 0.45, thresh: float = 60.0) -> None:
        """Darken pixels on strong colour edges inside the sprite (clean separations)."""
        c = self.a[..., :3].astype(float)
        lum = c @ np.array([0.3, 0.59, 0.11])
        m = self.opaque()
        right = np.roll(lum, -1, 1)
        down = np.roll(lum, -1, 0)
        e = ((lum - right) > thresh) | ((lum - down) > thresh)
        e &= m & np.roll(m, -1, 1) & np.roll(m, -1, 0)
        self.a[e, :3] = (c[e] * darken).astype(np.uint8)

    def paste(self, other: Canvas, ox: int, oy: int) -> None:
        im = self.img()
        im.alpha_composite(other.img(), (ox, oy))
        self.a = np.array(im)

    def img(self) -> Image.Image:
        return Image.fromarray(self.a, "RGBA")


def shift(m: np.ndarray, dx: int, dy: int) -> np.ndarray:
    out = np.zeros_like(m)
    h, w = m.shape
    ys = slice(max(dy, 0), h + min(dy, 0))
    xs = slice(max(dx, 0), w + min(dx, 0))
    yd = slice(max(-dy, 0), h + min(-dy, 0))
    xd = slice(max(-dx, 0), w + min(-dx, 0))
    out[ys, xs] = m[yd, xd]
    return out


def shift3(c: np.ndarray, dx: int, dy: int) -> np.ndarray:
    out = np.zeros_like(c)
    h, w = c.shape[:2]
    out[max(dy, 0) : h + min(dy, 0), max(dx, 0) : w + min(dx, 0)] = c[
        max(-dy, 0) : h + min(-dy, 0), max(-dx, 0) : w + min(-dx, 0)
    ]
    return out


def blur(a: np.ndarray, r: float) -> np.ndarray:
    im = Image.fromarray((a * 255).astype(np.uint8), "L").filter(ImageFilter.GaussianBlur(r))
    return np.array(im, float) / 255.0


def profile(w: int, base: float, amp: float, seed: int, rough: float = 0.55, peaks: int = 6) -> np.ndarray:
    """A 1D ridge line (y per x) by midpoint displacement: jagged mountains and cliffs."""
    rng = random.Random(seed)
    n = 1
    while n < w:
        n *= 2
    pts = [0.0] * (n + 1)
    pts[0], pts[n] = rng.uniform(-1, 1), rng.uniform(-1, 1)
    step, scale = n, 1.0
    while step > 1:
        half = step // 2
        for i in range(half, n, step):
            pts[i] = (pts[i - half] + pts[i + half]) / 2 + rng.uniform(-1, 1) * scale
        step, scale = half, scale * rough
    ys = np.array(pts[:w])
    ys = (ys - ys.min()) / max(ys.max() - ys.min(), 1e-6)
    return base - ys * amp


def save(img: Image.Image, out: Path, name: str, scale: int) -> None:
    w, h = img.size
    img.resize((w * scale, h * scale), Image.NEAREST).save(out / name)
