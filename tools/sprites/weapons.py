"""Weapons: icons for the blacksmith and the layers that put a weapon in the hero's hand.

One generated sheet (art/source/weapons.jpg, prompt in PROMPTS.md) holds every weapon, upright
and side by side. For each weapon this cuts its band out of the sheet and runs it through the
ASHEN pipeline twice:

- weapon_<id>.png: the icon, 36x36 at 2x, tilted like a Souls inventory icon;
- held_<id>.png: the weapon as the hero holds it, on the hero's own canvas (77x120 at 2x), so
  its grip lands on HERO_GRIP. The page stacks knight_front.png, held_<id>.png and
  hero_hand.png (his fingers, closed over the handle) in that order.

The hero's pose is weapon-agnostic: a lowered fist. Each weapon says how it sits in it: the
angle it is turned by, its length beside the hero, and whether the fingers close over it (a
gauntlet is worn, not held). Run after ronin.py, which draws the hero.

Usage:
  uv run --with pillow --with numpy --with scipy --with opencv-python-headless \\
      python tools/sprites/weapons.py src/hollow/adapters/web/static/sprites
"""

import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent.parent / "src"))
from generated import SRC, pixelate, scaled  # noqa: E402
from kit import Canvas  # noqa: E402

from hollow.domain.armory import WEAPONS  # noqa: E402

HERO = (77, 120)
HERO_GRIP = (51, 60)
"""Where the hero's empty sword hand closes, in hero pixels (77x120, drawn at 2x)."""
ICON = 36
"""Weapon icons are 36x36 at 2x (72 px on the page): thin blades need the room."""


@dataclass(frozen=True)
class Held:
    band: tuple[int, int]
    """Columns of the sheet that hold this weapon."""
    grip: tuple[int, int]
    """Where the hand closes, in sheet pixels (the weapon stands upright on the sheet)."""
    turn: float
    """Degrees counter-clockwise from upright to how the hero holds it."""
    length: int
    """The weapon's upright height beside the hero, in hero pixels."""
    hand: bool = True
    """Do his fingers close over it? A gauntlet is worn, so it covers the hand instead."""
    icon_turn: float = -45.0


ARSENAL: dict[str, Held] = {
    # blades lowered, tip forward: 180 points them down, 20 more swings the tip to the front
    "rusted-katana": Held((45, 124), (84, 640), 200, 60),
    "uchigatana": Held((227, 306), (266, 640), 200, 60),
    # head resting on the ground in front of him, haft up to the fist
    "warden-maul": Held((376, 611), (493, 772), 195, 62),
    # staffs planted upright beside him, rings above his hat brim
    "pilgrim-shakujo": Held((678, 793), (735, 400), 0, 112),
    "surveyor-shakujo": Held((875, 1034), (955, 400), 0, 112),
    # the gauntlet worn on the lowered forearm, fist down
    "golem-fist": Held((1094, 1304), (1200, 245), 180, 30, hand=False, icon_turn=-15),
    # wound round the wrist, hanging to the ground
    "wyrm-chain": Held((1377, 1498), (1437, 60), 0, 60, icon_turn=-20),
}


def cut(sheet: Image.Image, mask: np.ndarray, held: Held) -> tuple[Image.Image, tuple[int, int]]:
    """The weapon on transparency, cropped to itself, and its grip in the crop."""
    x0, x1 = held.band
    band = mask[:, x0:x1]
    ys = np.where(band.any(1))[0]
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    rgba = np.array(sheet.crop((x0, y0, x1, y1)).convert("RGBA"))
    rgba[..., 3] = np.where(band[y0:y1], 255, 0)
    return Image.fromarray(rgba), (held.grip[0] - x0, held.grip[1] - y0)


def turned(img: Image.Image, grip: tuple[int, int], degrees: float) -> tuple[Image.Image, tuple[int, int]]:
    """Rotate at full resolution (before pixelating, so edges stay clean); track the grip."""
    if not degrees:
        return img, grip
    marker = Image.new("L", img.size, 0)
    marker.putpixel(grip, 255)
    out = img.rotate(degrees, Image.BICUBIC, expand=True)
    m = np.array(marker.rotate(degrees, Image.NEAREST, expand=True))
    ys, xs = np.where(m > 0)
    if not len(xs):  # the single pixel can vanish under NEAREST; widen it and retry
        big = Image.new("L", img.size, 0)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                big.putpixel((min(max(grip[0] + dx, 0), img.width - 1),
                              min(max(grip[1] + dy, 0), img.height - 1)), 255)  # fmt: skip
        m = np.array(big.rotate(degrees, Image.NEAREST, expand=True))
        ys, xs = np.where(m > 0)
    alpha = np.array(out)[..., 3] > 127
    yy, xx = np.where(alpha)
    box = (int(xx.min()), int(yy.min()), int(xx.max()) + 1, int(yy.max()) + 1)
    return out.crop(box), (int(round(xs.mean())) - box[0], int(round(ys.mean())) - box[1])


def pixel(img: Image.Image, size: tuple[int, int], tmp: Path, name: str, *args: str) -> Image.Image:
    """Pixelate a weapon. Thin blades and shafts are one pixel wide at this size, so the speck
    cleanup stays off; the outline is drawn afterwards by finish()."""
    src = tmp / f"{name}.png"
    img.save(src)
    return finish(pixelate(src, tmp, "--width", str(size[0]), "--height", str(size[1]),
                           "--colors", "16", "--smooth", "0.4", "--gamma", "0.8",
                           "--chroma", "1.25", "--sharpen", "1.6", "--no-clean",
                           "--outline", "none", *args))  # fmt: skip


def finish(img: Image.Image) -> Image.Image:
    """A pixel of light along the top-left edges, then a dark selective outline: steel has to
    read against the hero's dark coat as well as on the blacksmith's shelf."""
    c = Canvas(img.width, img.height)
    c.a = np.array(img.convert("RGBA"))
    solid = c.opaque()
    lit = solid & ~(np.pad(solid, ((1, 0), (0, 0)))[:-1] & np.pad(solid, ((0, 0), (1, 0)))[:, :-1])
    rgb = c.a[..., :3].astype(float)
    c.a[lit, :3] = (rgb[lit] + (np.array([236, 222, 198]) - rgb[lit]) * 0.45).astype(np.uint8)
    c.outline(darken=0.22)
    return c.img()


def held_layer(img: Image.Image, grip: tuple[int, int], held: Held, upright_h: int, tmp: Path,
               name: str) -> Image.Image:  # fmt: skip
    """The weapon on the hero's canvas, its grip on HERO_GRIP."""
    s = held.length / upright_h
    w, h = max(1, round(img.width * s)), max(1, round(img.height * s))
    sprite = pixel(img, (w + 4, h + 4), tmp, name, "--preset", "character")
    # where the grip lands: the pipeline fits the art into the box less a 2 px pad, centred
    # horizontally and anchored to the bottom (pixelate.py, process()); finish() keeps the size
    ow, oh = sprite.width - 4, sprite.height - 4
    fx = (sprite.width - (ow + 4)) // 2 + 2 + grip[0] * ow / img.width
    fy = sprite.height - (oh + 4) + 2 + grip[1] * oh / img.height
    layer = Image.new("RGBA", HERO, (0, 0, 0, 0))
    layer.alpha_composite(sprite, (round(HERO_GRIP[0] - fx), round(HERO_GRIP[1] - fy)))
    return layer


def icon(img: Image.Image, held: Held, tmp: Path, name: str) -> Image.Image:
    tilted = img.rotate(held.icon_turn, Image.BICUBIC, expand=True)
    return pixel(tilted, (ICON, ICON), tmp, f"{name}-icon", "--preset", "item")


def hand(hero: Image.Image) -> Image.Image:
    """His fingers: the hero's own fist pixels around HERO_GRIP, drawn over the handle."""
    c = Canvas(*HERO)
    base = np.array(hero.convert("RGBA").resize(HERO, Image.NEAREST))
    gx, gy = HERO_GRIP
    near = ((c.xx - gx) / 3.2) ** 2 + ((c.yy - gy) / 3.6) ** 2 <= 1
    lum = base[..., :3].astype(float) @ np.array([0.3, 0.59, 0.11])
    fingers = near & (base[..., 3] > 0) & (lum > 70)  # the pale bandaged knuckles, not the coat
    c.a[fingers] = base[fingers]
    return c.img()


def build(out: Path) -> None:
    sys.path.insert(0, str(HERE / "pipeline"))
    import pixelate as pipeline

    sheet = Image.open(SRC / "weapons.jpg").convert("RGB")
    mask = pipeline.remove_background(np.array(sheet.convert("RGBA")), "auto", 18.0, 0.0005, True)
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        for weapon_id, held in ARSENAL.items():
            assert weapon_id in WEAPONS, weapon_id
            img, grip = cut(sheet, mask, held)
            scaled(icon(img, held, tmp, weapon_id), 2).save(out / f"weapon_{weapon_id}.png")
            upright_h = img.height
            img, grip = turned(img, grip, held.turn)
            layer = held_layer(img, grip, held, upright_h, tmp, weapon_id)
            scaled(layer, 2).save(out / f"held_{weapon_id}.png")
    scaled(hand(Image.open(out / "knight_front.png")), 2).save(out / "hero_hand.png")


if __name__ == "__main__":
    build(Path(sys.argv[1]))
