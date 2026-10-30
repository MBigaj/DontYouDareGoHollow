"""Items: the icons for estus, embers, souls, titanite and the rest, plus the blacksmith's anvil
and the hit slash.

One generated sheet (art/source/items.jpg, prompt in PROMPTS.md) holds every item, one per
cell of a 4x3 grid. This cuts each cell out, keeps the item and runs it through the ASHEN
pipeline the way weapons.py does (no speck cleanup, then a rim of light and an outline), at
ICON pixels square, saved at 2x. The soul also comes small, for the souls counters in running
text. The anvil is its own painting (art/source/anvil.jpg), cropped to the anvil and the top
of its stump. The slash is an effect, so it is drawn in code.

Usage:
  uv run --with pillow --with numpy --with scipy --with opencv-python-headless \\
      python tools/sprites/items.py src/hollow/adapters/web/static/sprites
"""

import sys
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from generated import SRC, pixelate, scaled  # noqa: E402
from kit import BAYER4, Canvas, blend, hx  # noqa: E402
from weapons import finish  # noqa: E402

ICON = 24
"""Item icons are 24x24 at 2x (48 px on the page)."""
SMALL = 14
"""The small soul for counters in running text: 14x14 at 2x (28 px)."""
GRID = (4, 3)
SHEET: dict[str, tuple[int, int]] = {
    # file name: (column, row) on the sheet
    "estus": (0, 0),
    "ember": (1, 0),
    "lens": (2, 0),
    "sign": (3, 0),
    "ring": (0, 1),
    "tome": (1, 1),
    "soul": (2, 1),
    "titanite_shard": (3, 1),
    "large_titanite_shard": (0, 2),
    "titanite_chunk": (1, 2),
    "titanite_slab": (2, 2),
}
GLOWS = {"ember", "soul"}
"""Light sources: no rim of light (they are the light), a softer outline."""
ITEM = ("--preset", "item", "--colors", "16", "--smooth", "0.4", "--gamma", "0.85",
        "--chroma", "1.2", "--sharpen", "1.4", "--no-clean", "--outline", "none")  # fmt: skip
ANVIL_CROP = (200, 20, 1220, 640)
"""The anvil, the hammer, the hot blank and the sparks, with the top band of the stump."""
ANVIL = (104, 64)


def items(sheet: Image.Image, mask: np.ndarray) -> dict[tuple[int, int], Image.Image]:
    """Each item on transparency, cropped to itself, keyed by its cell. A piece belongs to the
    cell its centre is in, so a tall item may reach into the cell above it."""
    from scipy.ndimage import center_of_mass, label

    lbl, n = label(mask)
    sizes = np.bincount(lbl.ravel())
    w, h = sheet.width / GRID[0], sheet.height / GRID[1]
    found: dict[tuple[int, int], np.ndarray] = {}
    for i, (cy, cx) in enumerate(center_of_mass(mask, lbl, range(1, n + 1)), start=1):
        if sizes[i] < 40:  # specks of background noise
            continue
        key = (int(cx // w), int(cy // h))
        found[key] = found.get(key, np.zeros_like(mask)) | (lbl == i)
    rgba = np.array(sheet.convert("RGBA"))
    out = {}
    for key, m in found.items():
        ys, xs = np.where(m)
        one = rgba.copy()
        one[..., 3] = np.where(m, 255, 0)
        box = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
        out[key] = Image.fromarray(one).crop(box)
    return out


def icon(img: Image.Image, size: int, tmp: Path, name: str, glow: bool) -> Image.Image:
    src = tmp / f"{name}.png"
    img.save(src)
    sprite = pixelate(src, tmp, *ITEM, "--width", str(size), "--height", str(size))
    if not glow:
        return finish(sprite)
    c = Canvas(sprite.width, sprite.height)
    c.a = np.array(sprite)
    c.outline(darken=0.45)
    return c.img()


def anvil(tmp: Path, pipeline: Any) -> Image.Image:
    """The background comes off the whole painting first: the crop cuts through the stump, and
    the pipeline would take the dark wood at its edge for background."""
    src = tmp / "anvil.png"
    painting = np.array(Image.open(SRC / "anvil.jpg").convert("RGBA"))
    painting[..., 3] = np.where(
        pipeline.remove_background(painting, "auto", 18.0, 0.0005, True), 255, 0
    )
    Image.fromarray(painting).crop(ANVIL_CROP).save(src)
    sprite = pixelate(src, tmp, "--preset", "equipment", "--width", str(ANVIL[0]),
                      "--height", str(ANVIL[1]), "--colors", "32", "--smooth", "0.6",
                      "--gamma", "0.9", "--chroma", "1.2", "--sharpen", "1.4")  # fmt: skip
    return finish(sprite)


def slash() -> Image.Image:
    """A crescent cut, white-hot at its heart and cooling to ember at its thin ends, 80x80."""
    n = 80
    c = Canvas(n, n)
    # a circle's arc from the upper right to the lower left, bulging toward the upper left
    cx, cy, r = 62.0, 62.0, 52.0
    d = np.hypot(c.xx - cx, c.yy - cy)
    ang = np.arctan2(c.yy - cy, c.xx - cx)  # -pi..pi; the arc runs from -pi/2 - 0.75 to -pi + 0.75
    lo, hi = -np.pi + 0.05, -np.pi / 2 - 0.05
    t = np.clip((ang - lo) / (hi - lo), 0, 1)  # 0 at the lower-left end, 1 at the upper-right
    along = np.sin(t * np.pi)  # thickest in the middle
    on = (ang >= lo) & (ang <= hi)
    width = 1.0 + 9.0 * along
    inner = r - width * 0.35
    outer = r + width * 0.65
    body = on & (d >= inner) & (d <= outer)
    heat = np.clip((d - inner) / np.maximum(outer - inner, 1e-6), 0, 1)  # 0 inside edge
    core = body & (heat > 0.35) & (heat < 0.85) & (along > 0.35)
    dither = BAYER4[c.yy % 4, c.xx % 4]
    ember, hot, white = hx("c46a1c"), hx("f6c55a"), hx("fff4e0")
    c.fill(body, ember)
    c.fill(body & (along + dither * 0.35 > 0.45), hot)
    c.fill(core, white)
    # a trail of embers off the thin ends
    for x, y in ((14, 40), (11, 46), (17, 33), (40, 13), (46, 11), (33, 17), (9, 52), (52, 9)):
        c.dot(x, y, blend(ember, hot, 0.5))
    return c.img()


def build(out: Path) -> None:
    sys.path.insert(0, str(HERE / "pipeline"))
    import pixelate as pipeline

    sheet = Image.open(SRC / "items.jpg").convert("RGB")
    mask = pipeline.remove_background(np.array(sheet.convert("RGBA")), "auto", 18.0, 0.0005, True)
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        cut = items(sheet, mask)
        for name, place in SHEET.items():
            img = cut[place]
            glow = name in GLOWS
            scaled(icon(img, ICON, tmp, name, glow), 2).save(out / f"item_{name}.png")
            if name == "soul":
                small = icon(img, SMALL, tmp, "soul-small", glow)
                scaled(small, 2).save(out / "item_soul_small.png")
        scaled(anvil(tmp, pipeline), 2).save(out / "anvil.png")
    scaled(slash(), 4).save(out / "slash.png")


if __name__ == "__main__":
    build(Path(sys.argv[1]))
