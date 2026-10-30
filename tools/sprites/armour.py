"""Armour: icons for the blacksmith and the layers that put each piece on the hero, plus the
Architect road's accent (a soul-cyan eye and scarf).

One generated sheet (art/source/armour.jpg, prompt in PROMPTS.md) holds the four pieces, one
per cell of a 2x2 grid: the hood, the pauldrons, the gauntlets and the greaves. For each piece:

- armour_<id>.png: the icon, 36x36 at 2x (72 px on the page), the whole piece (a pair stays a
  pair, like a Souls inventory icon);
- worn_<id>.png: the piece on the hero's canvas (77x120 at 2x). Pasting the painted pieces on
  him never sat right (his pose is three-quarter, the sheet's pieces are front-on), so each is
  painted onto his own silhouette instead: the regions below (in hero pixels) say where it
  sits, his own shading is kept, and the piece's material comes from ASHEN ramps matched to
  its painting, with its details in code (the hood's folds and frayed hem, the pauldrons'
  lames, rivets and sun disc, the gauntlets' plates and cyan seam, the greaves' scales and
  straps). Layers only add pixels, so the hood is worn under the kasa, framing his face, and
  the gauntlets bring their own fist (worn_golem-gauntlets_fist.png) to close over the
  weapon's handle in place of hero_hand.png.

The page stacks knight_front.png, accent_architect.png (on the Architect road), the worn pieces
(legs, chest, arms, head), the weapon and the fist (see partials/_hero.html). Run after
weapons.py, which makes hero_hand.png.

Usage:
  uv run --with pillow --with numpy --with scipy --with opencv-python-headless \\
      python tools/sprites/armour.py src/hollow/adapters/web/static/sprites
"""

import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent.parent / "src"))
from generated import SRC, scaled  # noqa: E402
from kit import ASH, IRON, LEATHER, Canvas, hx, shift  # noqa: E402
from weapons import HERO, ICON, pixel  # noqa: E402

from hollow.domain.armory import ARMOUR  # noqa: E402

CELLS: dict[str, tuple[int, int, int, int]] = {
    # the piece's cell on the sheet (x0, y0, x1, y1): everything in it is the icon
    "wanderer-hood": (100, 0, 640, 470),
    "warden-pauldrons": (740, 0, 1530, 445),
    "golem-gauntlets": (110, 466, 710, 1010),
    "wyrm-greaves": (870, 434, 1400, 1012),
}


# Each material in ASHEN ramps (palettes/ashen.hex via kit.py), matched to its painting.
CLOTH = ASH[2:8]
BRONZE = [hx(h) for h in ("1c120e", "3a2a14", "5a4020", "7a5a24", "a07a34", "c99a48")]
VERDIGRIS = [hx(h) for h in ("34462c", "52683e", "6e8a62")]
WYRM = [hx(h) for h in ("101520", "1b2230", "2b3646", "3e4c5e", "566a7e", "7a8fa3", "a9bccb")]
SHEEN = hx("563a7a")
"""The abyss violet glint on the wyrm scales."""

# Where each piece sits on the hero, in hero pixels (77x120; see knight_front.png at 1x).
EYE = (32, 14)
"""His one ember eye, under the brim."""
BRIM = 12
"""The first row under the kasa's brim."""
COWL = ((26, 12), (40, 12), (42, 16), (44, 22), (42, 26), (37, 24), (33, 26), (29, 24), (25, 26),
        (22, 22), (24, 16))  # fmt: skip
FACE = ((29, 11), (38, 11), (38, 15), (37, 20), (30, 20), (29, 15))
"""The opening of the hood: his face in shadow, with the eye."""
PAULDRONS = (
    ((20, 25), (23, 21), (28, 19), (32, 21), (31, 26), (27, 30), (21, 32), (19, 29)),
    ((40, 21), (44, 18), (49, 19), (52, 23), (51, 28), (46, 31), (41, 28)),
)
FOREARMS = (
    # the weapon arm, lowered: forearm, wrist seam row, fist
    ((46, 37), (52, 37), (54, 46), (54, 59), (47, 59), (45, 46)),
    # the arm across the sash: forearm and hand
    ((19, 40), (34, 39), (35, 46), (19, 47)),
)
WRISTS = ((47, 52, 46, 46), (26, 26, 42, 44))
"""The cyan seam on each gauntlet (x0, x1, y0, y1)."""
SHINS = (
    ((23, 93), (32, 93), (33, 114), (14, 114), (14, 106), (23, 106)),
    ((47, 94), (58, 94), (60, 119), (46, 119)),
)
STRAPS = ((99, 104), (100, 105))
"""Rows of the leather straps on each greave."""

SOUL = [hx(h) for h in ("101a2e", "1e3150", "34507a", "5a7fae", "4fb4d0", "9ee2ee", "e6fbff")]
"""Night blue into soul cyan (palettes/ashen.hex), for the Architect accent and the seams."""
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


def scarf_of(hero: np.ndarray) -> np.ndarray:
    """The scarf's pale warm cloth, which lies over everything at the neck and shoulder."""
    r, b = hero[..., 0].astype(int), hero[..., 2].astype(int)
    return Canvas(*HERO).poly(SCARF) & (r > b + 12) & (lum(hero) > 95) & (hero[..., 3] > 0)


def form(c: Canvas, hero: np.ndarray, mask: np.ndarray, weight: float) -> np.ndarray:
    """Lightness to paint `mask` with, 0..1: his own shading, mixed with the piece's own
    rounded form lit from the upper left (`weight` of it)."""
    own = np.clip((lum(hero) - 25) / 150, 0, 1)
    tmp = Canvas(*HERO)
    tmp.shade(mask, [np.array([v, v, v], np.uint8) for v in range(0, 256, 16)], dither=0)
    hgt = tmp.a[..., 0] / 255.0
    return np.where(hero[..., 3] > 0, own * (1 - weight) + hgt * weight, hgt)


def hood(c: Canvas, hero: np.ndarray) -> None:
    """A ragged cloth hood under the kasa, framing his face and falling to his shoulders, its
    iron cap's brow band just showing under the brim."""
    cowl = c.poly(COWL) & ~c.poly(FACE) & ~scarf_of(hero)
    rng = np.random.default_rng(3)
    for x in range(20, 47):  # a frayed hem: every other thread ends a little higher
        if x % 2:
            cowl[23 + int(rng.integers(0, 4)) :, x] = False
    val = form(c, hero, cowl, 0.7)
    val[(c.xx % 3 == 0) & (c.yy > 17)] *= 0.75  # folds
    c.levels(cowl, val, CLOTH, dither=0.4)
    band = c.rect((28, BRIM, 39, BRIM))
    c.fill(band, IRON[2])
    c.fill(band & (c.xx % 3 == 0), IRON[5])  # rivets


def pauldrons(c: Canvas, hero: np.ndarray) -> None:
    """Rounded bronze plates on both shoulders: three lames each, rivets along the rim, a sun
    disc on the top plate, green with verdigris. The scarf still lies over the right one."""
    for n, shape in enumerate(PAULDRONS):
        plate = c.poly(shape) & ~scarf_of(hero)
        c.shade(plate, BRONZE, light=(-0.6, -0.8), soft=2.0, lo=0.15, hi=0.85, dither=0.3)
        ys = np.where(plate.any(1))[0]
        top, bottom = int(ys.min()), int(ys.max())
        for k in (1, 2):  # the lames: a dark lower edge, the next plate's lit rim below it
            y = top + (bottom - top) * k // 3
            c.fill(plate & (c.yy == y), BRONZE[0])
            c.fill(plate & (c.yy == y + 1), BRONZE[4])
        rng = np.random.default_rng(n)
        patina = plate & (rng.random(plate.shape) < 0.2) & (c.yy > top + 1)
        c.levels(patina, np.clip((lum(c.a) - 40) / 120, 0, 1), VERDIGRIS, dither=0)
        xs = np.where(plate.any(0))[0]
        cx, cy = int(xs.mean()), top + (bottom - top) // 3
        c.fill(c.rect((cx - 1, cy - 1, cx, cy)) & plate, BRONZE[5])  # the sun disc
        c.fill(c.rect((cx, cy, cx, cy)) & plate, BRONZE[3])
        edge = plate & ~shift(plate, 0, 1)
        c.fill(edge & (c.xx % 2 == n % 2), BRONZE[4])  # rivets along the lower rim


def gauntlets(c: Canvas, hero: np.ndarray) -> None:
    """Riveted iron over both forearms and hands, plate lines every few rows, a faint cyan
    seam at the wrist. The iron follows his sleeves and hands, not the coat behind them."""
    from scipy.ndimage import binary_closing

    for shape, (x0, x1, y0, y1) in zip(FOREARMS, WRISTS, strict=True):
        arm = binary_closing(c.poly(shape) & (hero[..., 3] > 0) & (lum(hero) > 38))
        arm &= c.poly(shape) & (hero[..., 3] > 0)
        val = form(c, hero, arm, 0.35)
        c.levels(arm, val, IRON[1:7], dither=0.3)
        lines = arm & (c.yy < y0) & (x0 != x1)
        c.fill(lines & (c.yy % 4 == 1), IRON[1])  # plate lines on the lowered forearm
        c.fill(lines & (c.yy % 4 == 2) & (c.xx % 3 == 0), IRON[6])  # rivets
        seam = c.rect((x0, y0, x1, y1)) & arm
        c.fill(seam, SOUL[3])
        c.fill(seam & ((c.xx + c.yy) % 2 == 0), SOUL[4])


def greaves(c: Canvas, hero: np.ndarray) -> None:
    """Overlapping wyrm scales from knee to toe, two leather straps across each shin."""
    for shape, straps in zip(SHINS, STRAPS, strict=True):
        leg = c.poly(shape) & (hero[..., 3] > 0)
        val = form(c, hero, leg, 0.4) * 0.82  # as dark as the coat they stand under
        # scales: rows two pixels tall, every other row offset, each scale lit on top
        row = c.yy // 2
        tip = (c.yy % 2 == 1) & ((c.xx + (row % 2) * 2) % 4 == 0)
        crown = (c.yy % 2 == 0) & ((c.xx + (row % 2) * 2) % 4 == 2)
        val = np.where(tip, val * 0.45, np.where(crown, np.minimum(1, val + 0.3), val))
        c.levels(leg, val, WYRM, dither=0.2)
        c.fill(leg & crown & ((c.xx // 4 + row) % 3 == 0), SHEEN)  # an iridescent glint
        leather = LEATHER[2:5]
        for y in straps:
            band = leg & (c.yy == y)
            c.fill(band, leather[1])
            c.fill(band & (c.xx % 3 == 0), leather[2])


RAISED = {"wanderer-hood", "warden-pauldrons"}
"""Pieces that stand out from his body, so their outline parts them from it too."""

PAINTERS = {
    "wanderer-hood": hood,
    "warden-pauldrons": pauldrons,
    "golem-gauntlets": gauntlets,
    "wyrm-greaves": greaves,
}


def worn(armour_id: str, hero: np.ndarray) -> Image.Image:
    """The piece painted onto the hero's own silhouette, in its own colours, then outlined
    wherever it stands off his body."""
    c = Canvas(*HERO)
    PAINTERS[armour_id](c, hero)
    piece = c.opaque()
    c.outline(darken=0.25)
    if armour_id not in RAISED:  # flush with his limbs: outlined only against the background
        c.a[c.opaque() & ~piece & (hero[..., 3] > 0)] = 0
    return c.img()


def fist(hand_layer: Image.Image) -> Image.Image:
    """The gauntlet's fingers over the handle: hero_hand.png turned to iron."""
    a = np.array(hand_layer.convert("RGBA").resize(HERO, Image.NEAREST))
    recolour(a, a[..., 3] > 0, IRON, 20, 200)
    return Image.fromarray(a)


def accent(hero: np.ndarray) -> Image.Image:
    """The Architect road: his ember eye and his ash-white scarf turned soul cyan."""
    a = hero.copy()
    r = a[..., 0].astype(int)
    scarf = scarf_of(hero)
    eye = ellipse(*EYE, 1.6, 1.6) & (r > 150) & (a[..., 3] > 0)
    recolour(a, scarf, SOUL[1:6], 90, 230)
    a[eye, :3] = SOUL[5]
    a[eye & (lum(hero) > 200), :3] = SOUL[6]
    a[~(scarf | eye)] = 0
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
            scaled(worn(armour_id, hero), 2).save(out / f"worn_{armour_id}.png")
    scaled(fist(Image.open(out / "hero_hand.png")), 2).save(out / "worn_golem-gauntlets_fist.png")
    scaled(accent(hero), 2).save(out / "accent_architect.png")


if __name__ == "__main__":
    build(Path(sys.argv[1]))
