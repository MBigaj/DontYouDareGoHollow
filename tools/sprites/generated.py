"""Shared steps for generated art: run a painting through the ASHEN pipeline, scale it, and
build the landmark overlays (hover glow, fog veil) that make painted places clickable.

Used by ronin.py and architect.py. Sources live in art/source/ (prompts in PROMPTS.md).
"""

import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from kit import BAYER4, Canvas, hx

HERE = Path(__file__).parent
SRC = HERE / "art" / "source"
PIXELATE = HERE / "pipeline" / "pixelate.py"


def pixelate(src: Path, tmp: Path, *args: str) -> Image.Image:
    """Run the ASHEN pipeline on one source and return the native-size sprite."""
    out = tmp / src.stem
    subprocess.run([sys.executable, str(PIXELATE), str(src), "--out", str(out), "--preview", "1", *args],
                   check=True, stdout=subprocess.DEVNULL)  # fmt: skip
    return Image.open(out / f"{src.stem}_px.png").convert("RGBA")


def cropped(src: Path, box: tuple[int, int, int, int], tmp: Path) -> Path:
    path = tmp / f"{src.stem}.png"
    Image.open(src).convert("RGB").crop(box).save(path)
    return path


def scaled(img: Image.Image, k: int) -> Image.Image:
    return img.resize((img.width * k, img.height * k), Image.NEAREST)


def landmark_masks(src: Path, crop: tuple[int, int, int, int], grid: tuple[int, int],
                   areas: dict[str, tuple[tuple[int, int], ...]]) -> dict[str, np.ndarray]:  # fmt: skip
    """Each landmark's silhouette at the map's native size (2x the atlas grid).

    The atlas area is a rough outline; GrabCut on the full-size painting snaps it to the
    painted building, so the hover outline follows the roofs and towers."""
    import cv2  # the pipeline already needs OpenCV
    from PIL import ImageDraw

    cv2.setRNGSeed(0)
    painting = Image.open(src).convert("RGB").crop(crop)
    bgr = cv2.cvtColor(np.array(painting), cv2.COLOR_RGB2BGR)
    kx, ky = painting.width / grid[0], painting.height / grid[1]
    native = (grid[0] * 2, grid[1] * 2)
    masks = {}
    for key, area in areas.items():
        rough = Image.new("L", painting.size, 0)
        ImageDraw.Draw(rough).polygon([(x * kx, y * ky) for x, y in area], fill=255)
        inside = np.array(rough) > 0
        u8 = inside.astype(np.uint8)
        mask = np.full(inside.shape, cv2.GC_BGD, np.uint8)
        mask[cv2.dilate(u8, np.ones((25, 25), np.uint8)) > 0] = cv2.GC_PR_BGD
        mask[inside] = cv2.GC_PR_FGD
        mask[cv2.erode(u8, np.ones((31, 31), np.uint8)) > 0] = cv2.GC_FGD
        bgd, fgd = np.zeros((1, 65)), np.zeros((1, 65))
        cv2.grabCut(bgr, mask, None, bgd, fgd, 6, cv2.GC_INIT_WITH_MASK)
        fg = ((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD)).astype(np.uint8)
        fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
        n, labels, stats, _ = cv2.connectedComponentsWithStats(fg)
        if n > 1:  # keep the landmark, drop stray scraps
            fg = (labels == 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])).astype(np.uint8)
        small = Image.fromarray(fg * 255).resize(native, Image.BOX)
        masks[key] = np.array(small) > 127
    return masks


def ring(m: np.ndarray) -> np.ndarray:
    """The pixels just outside a mask (4-neighbourhood), without wrapping round the edges."""
    p = np.pad(m, 1)
    near = p[:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, :-2] | p[1:-1, 2:]
    return near & ~m


GOLD = (hx("f6d98a"), hx("c8963c"))
CYAN = (hx("e6fbff"), hx("4fb4d0"))


def glow(art: Image.Image, m: np.ndarray, line: tuple[np.ndarray, np.ndarray] = GOLD) -> Image.Image:
    """Shown on hover: the landmark lifted a step, a two-tone outline and a dark rim."""
    c = Canvas(m.shape[1], m.shape[0])
    base = np.array(art.convert("RGBA").resize((c.w, c.h), Image.NEAREST))
    lifted = base[..., :3].astype(float) * 1.12 + np.array([16, 10, 0])
    c.a[m, :3] = lifted[m].round().clip(0, 255).astype(np.uint8)
    c.a[m, 3] = 255
    first = ring(m)
    second = ring(m | first)
    c.fill(first, line[0])
    c.fill(second, line[1])
    c.fill(ring(m | first | second), hx("1a0f08"))
    return scaled(c.img(), 2)


DUSK_FOG = (hx("9a96a4"), 1.0, 0.38)
"""Ronin road: the landmark drained of colour under pale drifting mist."""
NIGHT_FOG = (hx("1c2433"), 0.7, 0.45)
"""Architect road: the landmark sunk into dark, cold night fog."""


def veil(art: Image.Image, m: np.ndarray,
         fog: tuple[np.ndarray, float, float] = DUSK_FOG) -> Image.Image:  # fmt: skip
    """Shown while a region is in the fog: the landmark drained of colour under drifting mist."""
    c = Canvas(m.shape[1], m.shape[0])
    base = np.array(art.convert("RGBA").resize((c.w, c.h), Image.NEAREST))[..., :3].astype(float)
    lum = base @ np.array([0.3, 0.59, 0.11])
    mist = np.sin(c.xx * 0.21 + c.yy * 0.09) + np.sin(c.yy * 0.33 - c.xx * 0.05)
    t = np.clip(0.55 + 0.12 * mist, 0, 1) + (BAYER4[c.yy % 4, c.xx % 4] - 0.5) * 0.2
    tint, dim, mix = fog
    grey = lum[..., None] * np.array([0.9, 0.92, 1.0]) * dim
    out = grey + (np.array(tint, float) - grey) * np.clip(t, 0, 1)[..., None] * mix
    c.a[m, :3] = out[m].round().clip(0, 255).astype(np.uint8)
    c.a[m, 3] = 255
    return scaled(c.img(), 2)
