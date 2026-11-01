"""Armour: icons for the blacksmith and the layers that put each piece on the hero, plus the
Architect road's accent (a soul-cyan eye and scarf).

One generated sheet (art/source/armour.jpg, prompt in PROMPTS.md) holds the four pieces, one
per cell of a 2x2 grid: the hood, the pauldrons, the gauntlets and the greaves. For each piece:

- armour_<id>.png: the icon, 36x36 at 2x (72 px on the page), the whole piece (a pair stays a
  pair, like a Souls inventory icon);
- worn_<id>.png: the piece on the hero's canvas (77x120 at 2x). Pasting the painted pieces on
  him never sat right (his pose is three-quarter, the sheet's pieces are front-on), so each is
  painted onto his own silhouette instead: where it sits is its SLOT's fit (FITS, saved
  once per slot and shared by every piece of that slot), his own shading is kept, and the piece's material comes from ASHEN ramps matched to
  its painting, with its details in code (the hood's folds and frayed hem, the pauldrons'
  lames, rivets and sun disc, the gauntlets' plates and cyan seam, the greaves' scales and
  straps; LOOKS). Layers only add pixels, so head pieces are worn under the kasa, and every
  arms piece brings its own fist (worn_<id>_fist.png) to close over the weapon's handle in
  place of hero_hand.png.

A new piece: add it to ARMOUR in hollow.domain.armory, then a LOOKS entry here (its icon's
sheet and cell, and a painter). Its position comes from its slot; never move a fit for one
piece.

The page stacks knight_front.png, accent_architect.png (on the Architect road), the worn pieces
(legs, chest, arms, head), the weapon and the fist (see partials/_hero.html). Run after
weapons.py, which makes hero_hand.png.

Usage:
  uv run --with pillow --with numpy --with scipy --with opencv-python-headless \\
      python tools/sprites/armour.py src/hollow/adapters/web/static/sprites
"""

import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
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
from hollow.domain.events import Slot  # noqa: E402

Point = tuple[int, int]
Box = tuple[int, int, int, int]
"""x0, y0, x1, y1, inclusive."""

# ---------------------------------------------------------------- where each slot sits on him
# All in hero pixels (77x120: knight_front.png at 1x). These fits belong to the SLOT, not to a
# piece: every head piece is painted inside the head's fit, every pair of greaves inside the
# legs' fit, and so on. A new piece only brings its look (colours and details, LOOKS below).
# Change a fit only when the hero himself is redrawn, then rerun this script for every piece.

EYE = (32, 14)
"""His one ember eye, under the brim. Head pieces always leave it showing."""
SCARF = ((38, 12), (73, 12), (73, 45), (38, 45))
"""The box the trailing scarf lies in. Head and chest pieces lie under it."""


@dataclass(frozen=True)
class Fit:
    shapes: tuple[tuple[Point, ...], ...]
    """The piece's area, one polygon per side (a left and a right pauldron, two greaves)."""
    bands: tuple[tuple[Box, ...], ...]
    """Per shape, the boxes for the slot's band detail: the brow band under the brim, the
    wrist seam, the straps across the shin."""
    holes: tuple[tuple[Point, ...], ...] = ()
    """Areas always left open (his face under the hood)."""
    on_body: bool = True
    """Clipped to his silhouette (a sleeve, a shin), else free to stand off it (a hood's
    drape, a pauldron's rim)."""
    limb_only: bool = False
    """Only his lighter sleeve and hand, not the dark coat behind them inside the shape."""
    under_scarf: bool = False
    """The scarf stays on top (it is left out of the piece)."""
    raised: bool = False
    """Stands out from his body: its outline parts it from him too, not only from the
    background."""


FITS: dict[Slot, Fit] = {
    # under the kasa (layers only add pixels, so nothing can sit over the hat), framing his
    # face and falling to his shoulders; the brow band is the row just under the brim
    Slot.HEAD: Fit(
        shapes=(((26, 12), (40, 12), (42, 16), (44, 22), (42, 26), (37, 24), (33, 26),
                 (29, 24), (25, 26), (22, 22), (24, 16)),),  # fmt: skip
        bands=(((28, 12, 39, 12),),),
        holes=(((29, 11), (38, 11), (38, 15), (37, 20), (30, 20), (29, 15)),),
        on_body=False,
        under_scarf=True,
        raised=True,
    ),
    # on the shoulder line of the coat, left and right; the band is unused (lames are spaced
    # down each plate)
    Slot.CHEST: Fit(
        shapes=(
            ((20, 25), (23, 21), (28, 19), (32, 21), (31, 26), (27, 30), (21, 32), (19, 29)),
            ((40, 21), (44, 18), (49, 19), (52, 23), (51, 28), (46, 31), (41, 28)),
        ),
        bands=((), ()),
        on_body=False,
        under_scarf=True,
        raised=True,
    ),
    # the lowered weapon arm (forearm and fist) and the arm across the sash (forearm and
    # hand); the band is the wrist. Arms pieces also close their own fist over the weapon's
    # handle (worn_<id>_fist.png, from hero_hand.png), in place of his bare fingers.
    Slot.ARMS: Fit(
        shapes=(
            ((46, 37), (52, 37), (54, 46), (54, 59), (47, 59), (45, 46)),
            ((19, 40), (34, 39), (35, 46), (19, 47)),
        ),
        bands=(((47, 46, 52, 46),), ((26, 42, 26, 44),)),
        limb_only=True,
    ),
    # knee to toe on both legs, his feet pointing out; the bands are the straps' rows
    Slot.LEGS: Fit(
        shapes=(
            ((23, 93), (32, 93), (33, 114), (14, 114), (14, 106), (23, 106)),
            ((47, 94), (58, 94), (60, 119), (46, 119)),
        ),
        bands=(((0, 99, 76, 99), (0, 104, 76, 104)), ((0, 100, 76, 100), (0, 105, 76, 105))),
    ),
}

# ---------------------------------------------------------------- what each piece looks like
# Materials in ASHEN ramps (palettes/ashen.hex via kit.py), matched to each painting.
CLOTH = ASH[2:8]
BRONZE = [hx(h) for h in ("1c120e", "3a2a14", "5a4020", "7a5a24", "a07a34", "c99a48")]
VERDIGRIS = [hx(h) for h in ("34462c", "52683e", "6e8a62")]
WYRM = [hx(h) for h in ("101520", "1b2230", "2b3646", "3e4c5e", "566a7e", "7a8fa3", "a9bccb")]
SHEEN = hx("563a7a")
"""The abyss violet glint on the wyrm scales."""
SOUL = [hx(h) for h in ("101a2e", "1e3150", "34507a", "5a7fae", "4fb4d0", "9ee2ee", "e6fbff")]
"""Night blue into soul cyan, for the Architect accent and the gauntlets' seam."""

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


Painter = Callable[[Canvas, np.ndarray, Fit], None]


def hood(c: Canvas, hero: np.ndarray, fit: Fit) -> None:
    """A ragged cloth hood under the kasa, framing his face and falling to his shoulders, its
    iron cap's brow band just showing under the brim."""
    cowl = area(c, hero, fit, 0)
    ys, xs = np.where(cowl.any(1))[0], np.where(cowl.any(0))[0]
    rng = np.random.default_rng(3)
    for x in range(int(xs.min()) - 2, int(xs.max()) + 3):  # a frayed hem: every other thread
        # ends a little higher
        if x % 2:
            cowl[int(ys.max()) - 3 + int(rng.integers(0, 4)) :, x] = False
    val = form(c, hero, cowl, 0.7)
    val[(c.xx % 3 == 0) & (c.yy > int(ys.min()) + 5)] *= 0.75  # folds
    c.levels(cowl, val, CLOTH, dither=0.4)
    for box in fit.bands[0]:
        band = c.rect(box)
        c.fill(band, IRON[2])
        c.fill(band & (c.xx % 3 == 0), IRON[5])  # rivets


def pauldrons(c: Canvas, hero: np.ndarray, fit: Fit) -> None:
    """Rounded bronze plates on both shoulders: three lames each, rivets along the rim, a sun
    disc on the top plate, green with verdigris. The scarf still lies over the right one."""
    for n in range(len(fit.shapes)):
        plate = area(c, hero, fit, n)
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


def gauntlets(c: Canvas, hero: np.ndarray, fit: Fit) -> None:
    """Riveted iron over both forearms and hands, plate lines every few rows, a faint cyan
    seam at the wrist. The iron follows his sleeves and hands, not the coat behind them."""
    for n in range(len(fit.shapes)):
        arm = area(c, hero, fit, n)
        val = form(c, hero, arm, 0.35)
        c.levels(arm, val, IRON[1:7], dither=0.3)
        for x0, y0, x1, y1 in fit.bands[n]:
            lines = arm & (c.yy < y0) & (x0 != x1)  # plates only along a lowered forearm
            c.fill(lines & (c.yy % 4 == 1), IRON[1])
            c.fill(lines & (c.yy % 4 == 2) & (c.xx % 3 == 0), IRON[6])  # rivets
            seam = c.rect((x0, y0, x1, y1)) & arm
            c.fill(seam, SOUL[3])
            c.fill(seam & ((c.xx + c.yy) % 2 == 0), SOUL[4])


def greaves(c: Canvas, hero: np.ndarray, fit: Fit) -> None:
    """Overlapping wyrm scales from knee to toe, two leather straps across each shin."""
    for n in range(len(fit.shapes)):
        leg = area(c, hero, fit, n)
        val = form(c, hero, leg, 0.4) * 0.82  # as dark as the coat they stand under
        # scales: rows two pixels tall, every other row offset, each scale lit on top
        row = c.yy // 2
        tip = (c.yy % 2 == 1) & ((c.xx + (row % 2) * 2) % 4 == 0)
        crown = (c.yy % 2 == 0) & ((c.xx + (row % 2) * 2) % 4 == 2)
        val = np.where(tip, val * 0.45, np.where(crown, np.minimum(1, val + 0.3), val))
        c.levels(leg, val, WYRM, dither=0.2)
        c.fill(leg & crown & ((c.xx // 4 + row) % 3 == 0), SHEEN)  # an iridescent glint
        leather = LEATHER[2:5]
        for box in fit.bands[n]:
            band = leg & c.rect(box)
            c.fill(band, leather[1])
            c.fill(band & (c.xx % 3 == 0), leather[2])


STONE = ASH[2:8]
LICHEN = [hx(h) for h in ("34462c", "52683e", "7e9460")]


def stone_helm(c: Canvas, hero: np.ndarray, fit: Fit) -> None:
    """A cowl of grey stone under the kasa, cracked and grown over with lichen, two short
    curled horns at its temples and a corroded bronze rim at the brow."""
    cowl = area(c, hero, fit, 0)
    ys, xs = np.where(cowl.any(1))[0], np.where(cowl.any(0))[0]
    top, bottom, left, right = int(ys.min()), int(ys.max()), int(xs.min()), int(xs.max())
    c.shade(cowl, STONE, light=(-0.6, -0.8), soft=2.0, lo=0.2, hi=0.85, dither=0.3)
    rng = np.random.default_rng(11)
    for _ in range(5):  # cracks
        x, y = int(rng.integers(left + 2, right - 2)), int(rng.integers(top + 3, bottom - 2))
        for k in range(int(rng.integers(2, 5))):
            if 0 <= y + k < c.h and cowl[y + k, x + (k % 2)]:
                c.dot(x + (k % 2), y + k, STONE[0])
    moss = cowl & (rng.random(cowl.shape) < 0.07) & (c.yy > top + 2)
    c.levels(moss, np.clip((lum(c.a) - 40) / 120, 0, 1), LICHEN, dither=0)
    for side, x in ((-1, left), (1, right)):  # horns curling out from the temples
        for k, (dx, dy) in enumerate(((0, 0), (side, -1), (2 * side, -1), (3 * side, 0),
                                      (3 * side, 1))):  # fmt: skip
            c.dot(x + dx, top + 3 + dy, STONE[4 - min(k, 3)])
    for box in fit.bands[0]:
        band = c.rect(box)
        c.fill(band, BRONZE[2])
        c.fill(band & (c.xx % 3 == 0), VERDIGRIS[1])


@dataclass(frozen=True)
class Look:
    """How one piece is drawn: where its icon is, how it is painted inside its slot's fit."""

    sheet: str
    """Its painting in art/source/."""
    cell: Box
    """Its cell on that sheet: everything in it is the icon."""
    paint: Painter
    fist: list[np.ndarray] | None = None
    """For arms pieces: the ramp its fingers over the weapon's handle are recoloured to."""


HELM_CELL = (700, 220, 1400, 880)
"""The helm's half of gargoyle_gear.jpg (the halberd stands in the left third)."""

LOOKS: dict[str, Look] = {
    "wanderer-hood": Look("armour.jpg", (100, 0, 640, 470), hood),
    "warden-pauldrons": Look("armour.jpg", (740, 0, 1530, 445), pauldrons),
    "golem-gauntlets": Look("armour.jpg", (110, 466, 710, 1010), gauntlets, fist=IRON),
    "wyrm-greaves": Look("armour.jpg", (870, 434, 1400, 1012), greaves),
    # the Plain-Form Gargoyle's drop, on the sheet it shares with his halberd
    "gargoyle-helm": Look("gargoyle_gear.jpg", HELM_CELL, stone_helm),
}


def area(c: Canvas, hero: np.ndarray, fit: Fit, n: int) -> np.ndarray:
    """Shape `n` of a fit, with its rules applied: holes cut, the scarf left on top, clipped
    to his silhouette (and, on his limbs, to the limb rather than the dark coat behind it)."""
    mask = c.poly(fit.shapes[n])
    for hole in fit.holes:
        mask &= ~c.poly(hole)
    if fit.under_scarf:
        mask &= ~scarf_of(hero)
    if fit.on_body:
        mask &= hero[..., 3] > 0
    if fit.limb_only:
        from scipy.ndimage import binary_closing

        mask = binary_closing(mask & (lum(hero) > 38)) & mask
    return mask


def worn(armour_id: str, hero: np.ndarray) -> Image.Image:
    """The piece painted onto the hero's own silhouette inside its slot's fit, in its own
    colours, then outlined wherever it stands off his body."""
    fit = FITS[ARMOUR[armour_id].slot]
    c = Canvas(*HERO)
    LOOKS[armour_id].paint(c, hero, fit)
    piece = c.opaque()
    c.outline(darken=0.25)
    if not fit.raised:  # flush with his limbs: outlined only against the background
        c.a[c.opaque() & ~piece & (hero[..., 3] > 0)] = 0
    return c.img()


def fist(hand_layer: Image.Image, ramp: list[np.ndarray]) -> Image.Image:
    """An arms piece's fingers over the weapon's handle: hero_hand.png in its metal."""
    a = np.array(hand_layer.convert("RGBA").resize(HERO, Image.NEAREST))
    recolour(a, a[..., 3] > 0, ramp, 20, 200)
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

    missing = set(ARMOUR) ^ set(LOOKS)
    assert not missing, f"every piece in hollow.domain.armory.ARMOUR needs a LOOKS entry: {missing}"
    hero = np.array(Image.open(out / "knight_front.png").convert("RGBA").resize(HERO, Image.NEAREST))
    hand = Image.open(out / "hero_hand.png")
    sheets: dict[str, tuple[Image.Image, np.ndarray]] = {}
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        for armour_id, look in LOOKS.items():
            if look.sheet not in sheets:
                sheet = Image.open(SRC / look.sheet).convert("RGB")
                mask = pipeline.remove_background(np.array(sheet.convert("RGBA")), "auto", 18.0,
                                                  0.0005, True)  # fmt: skip
                sheets[look.sheet] = (sheet, mask)
            sheet, mask = sheets[look.sheet]
            icon = pixel(cut(sheet, mask, look.cell), (ICON, ICON), tmp, f"{armour_id}-icon",
                         "--preset", "item")  # fmt: skip
            scaled(icon, 2).save(out / f"armour_{armour_id}.png")
            scaled(worn(armour_id, hero), 2).save(out / f"worn_{armour_id}.png")
            if ARMOUR[armour_id].slot is Slot.ARMS:
                assert look.fist, f"{armour_id} covers his hands, so it needs a fist ramp"
                scaled(fist(hand, look.fist), 2).save(out / f"worn_{armour_id}_fist.png")
    scaled(accent(hero), 2).save(out / "accent_architect.png")


if __name__ == "__main__":
    build(Path(sys.argv[1]))
