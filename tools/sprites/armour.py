"""Armour: icons for the blacksmith and the layers that put each piece on the hero, plus the
Architect road's accent (a soul-cyan eye and scarf).

One generated sheet (art/source/armour.jpg, prompt in PROMPTS.md) holds the four pieces, one
per cell of a 2x2 grid: the hood, the pauldrons, the gauntlets and the greaves. For each piece:

- armour_<id>.png: the icon, 36x36 at 2x (72 px on the page), the whole piece (a pair stays a
  pair, like a Souls inventory icon);
- worn_<id>.png: the piece on the hero's canvas (77x120 at 2x). Each part of it (one pauldron,
  one greave) is cut from the sheet, pixelated at its size beside the hero and set where it
  sits on him (WORN). Layers only add pixels, so the hood is worn under the kasa: the layer
  carries the hat's own pixels back over it and leaves a hole for his eye. The gauntlets turn
  his hands to iron instead of covering them with a sticker, and bring their own fist
  (worn_golem-gauntlets_fist.png) to close over the weapon's handle in place of hero_hand.png.

The page stacks knight_front.png, accent_architect.png (on the Architect road), the worn pieces
(legs, chest, arms, head), the weapon and the fist (see partials/_hero.html). Run after
weapons.py, which makes hero_hand.png.

Usage:
  uv run --with pillow --with numpy --with scipy --with opencv-python-headless \\
      python tools/sprites/armour.py src/hollow/adapters/web/static/sprites
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
from generated import SRC, scaled  # noqa: E402
from kit import IRON, Canvas, hx  # noqa: E402
from weapons import HERO, HERO_GRIP, ICON, pixel  # noqa: E402

from hollow.domain.armory import ARMOUR  # noqa: E402

CELLS: dict[str, tuple[int, int, int, int]] = {
    # the piece's cell on the sheet (x0, y0, x1, y1): everything in it is the icon
    "wanderer-hood": (100, 0, 640, 470),
    "warden-pauldrons": (740, 0, 1530, 445),
    "golem-gauntlets": (110, 466, 710, 1010),
    "wyrm-greaves": (870, 434, 1400, 1012),
}


@dataclass(frozen=True)
class Part:
    box: tuple[int, int, int, int]
    """Where the part is on the sheet."""
    width: int
    """Its width beside the hero, in hero pixels."""
    centre: int
    """The column of the hero it is centred on."""
    top: int
    """The row of the hero its top lands on."""
    keep: float = 1.0
    """How much of it to keep from the top (a gauntlet's cuff without the hand)."""
    turn: float = 0.0


WORN: dict[str, tuple[Part, ...]] = {
    # the hood under the kasa: its iron cap hidden by the brim, the cloth framing his face
    "wanderer-hood": (Part((100, 0, 640, 470), 25, 35, 6),),
    # one plate on each shoulder; the strap between them is hidden by the coat
    "warden-pauldrons": (
        Part((760, 0, 1040, 445), 13, 22, 19),
        Part((1230, 0, 1510, 445), 13, 49, 16),
    ),
    # the cuffs on both forearms: the lowered weapon arm and the arm across the sash
    "golem-gauntlets": (
        Part((415, 468, 700, 1000), 9, 51, 42, keep=0.5),
        Part((120, 468, 410, 1000), 10, 25, 40, keep=0.5, turn=-80),
    ),
    "wyrm-greaves": (
        Part((885, 436, 1135, 1010), 11, 24, 92),
        Part((1140, 436, 1380, 1010), 10, 54, 94),
    ),
}

KASA_ROWS = 11
"""The kasa fills the hero's rows down to this one."""
EYE = (33, 14)
HANDS = ((HERO_GRIP[0], HERO_GRIP[1] - 4, 4.2, 4.6), (24, 45, 3.5, 3.0))
"""The fists the gauntlets cover: the weapon hand and the hand on the sash (x, y, rx, ry)."""

SOUL = [hx(h) for h in ("101a2e", "1e3150", "34507a", "5a7fae", "4fb4d0", "9ee2ee", "e6fbff")]
"""Night blue into soul cyan (palettes/ashen.hex), for the Architect accent."""
SCARF = ((38, 12), (73, 12), (73, 45), (38, 45))
"""The box the trailing scarf lies in, on the hero."""


def cut(sheet: Image.Image, mask: np.ndarray, box: tuple[int, int, int, int]) -> Image.Image:
    """Everything of the sheet's subject inside `box`, on transparency, cropped to itself."""
    x0, y0, x1, y1 = box
    m = mask[y0:y1, x0:x1]
    rgba = np.array(sheet.crop(box).convert("RGBA"))
    rgba[..., 3] = np.where(m, 255, 0)
    ys, xs = np.where(m)
    return Image.fromarray(rgba).crop((int(xs.min()), int(ys.min()), int(xs.max()) + 1,
                                       int(ys.max()) + 1))  # fmt: skip


def lum(a: np.ndarray) -> np.ndarray:
    return a[..., :3].astype(float) @ np.array([0.3, 0.59, 0.11])


def recolour(a: np.ndarray, where: np.ndarray, ramp: list[np.ndarray], lo: float, hi: float) -> None:
    """Map the pixels in `where` onto `ramp` by their lightness, keeping the shading."""
    idx = np.clip(((lum(a) - lo) / (hi - lo) * len(ramp)).astype(int), 0, len(ramp) - 1)
    for i, col in enumerate(ramp):
        a[where & (idx == i), :3] = col


def ellipse(cx: float, cy: float, rx: float, ry: float) -> np.ndarray:
    yy, xx = np.mgrid[0 : HERO[1], 0 : HERO[0]]
    return ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2 <= 1


def worn(armour_id: str, sheet: Image.Image, mask: np.ndarray, hero: np.ndarray,
         tmp: Path) -> Image.Image:  # fmt: skip
    layer = Image.new("RGBA", HERO, (0, 0, 0, 0))
    for n, part in enumerate(WORN[armour_id]):
        img = cut(sheet, mask, part.box)
        if part.keep < 1:
            img = img.crop((0, 0, img.width, round(img.height * part.keep)))
        if part.turn:
            img = img.rotate(part.turn, Image.BICUBIC, expand=True)
        h = round(img.height * part.width / img.width)
        sprite = pixel(img, (part.width + 4, h + 4), tmp, f"{armour_id}-{n}", "--preset", "character")
        layer.alpha_composite(sprite, (part.centre - sprite.width // 2, part.top - 2))
    a = np.array(layer)
    opaque = hero[..., 3] > 0
    if armour_id == "wanderer-hood":
        yy, xx = np.mgrid[0 : HERO[1], 0 : HERO[0]]
        kasa = (yy <= KASA_ROWS) & opaque
        a[kasa] = hero[kasa]
        eye = ellipse(*EYE, 1.5, 1.5)
        a[eye] = 0  # his eye shows through (ember, or cyan on the Architect road)
    if armour_id == "golem-gauntlets":
        for hand in HANDS:
            near = ellipse(*hand) & opaque
            a[near] = hero[near]
            recolour(a, near, IRON, 20, 200)
    return Image.fromarray(a)


def fist(hand_layer: Image.Image) -> Image.Image:
    """The gauntlet's fingers over the handle: hero_hand.png turned to iron."""
    a = np.array(hand_layer.convert("RGBA").resize(HERO, Image.NEAREST))
    recolour(a, a[..., 3] > 0, IRON, 20, 200)
    return Image.fromarray(a)


def accent(hero: np.ndarray) -> Image.Image:
    """The Architect road: his ember eye and his ash-white scarf turned soul cyan."""
    c = Canvas(*HERO)
    a = hero.copy()
    r, g, b = (a[..., i].astype(int) for i in range(3))
    warm = (r > b + 12) & (lum(a) > 95)
    scarf = c.poly(SCARF) & warm & (a[..., 3] > 0)
    eye = ellipse(*EYE, 1.6, 1.6) & (r > 150) & (a[..., 3] > 0)
    recolour(a, scarf, SOUL[1:6], 90, 230)
    a[eye, :3] = SOUL[5]
    a[eye & (lum(hero) > 200), :3] = SOUL[6]
    keep = scarf | eye
    a[~keep] = 0
    return Image.fromarray(a)


def build(out: Path) -> None:
    sys.path.insert(0, str(HERE / "pipeline"))
    import pixelate as pipeline

    sheet = Image.open(SRC / "armour.jpg").convert("RGB")
    mask = pipeline.remove_background(np.array(sheet.convert("RGBA")), "auto", 18.0, 0.0005, True)
    hero = np.array(Image.open(out / "knight_front.png").convert("RGBA").resize(HERO, Image.NEAREST))
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        for armour_id in ARMOUR:
            icon = pixel(cut(sheet, mask, CELLS[armour_id]), (ICON, ICON), tmp,
                         f"{armour_id}-icon", "--preset", "item")  # fmt: skip
            scaled(icon, 2).save(out / f"armour_{armour_id}.png")
            scaled(worn(armour_id, sheet, mask, hero, tmp), 2).save(out / f"worn_{armour_id}.png")
    scaled(fist(Image.open(out / "hero_hand.png")), 2).save(out / "worn_golem-gauntlets_fist.png")
    scaled(accent(hero), 2).save(out / "accent_architect.png")


if __name__ == "__main__":
    build(Path(sys.argv[1]))
