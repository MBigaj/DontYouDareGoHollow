"""Ronin road art: generated source paintings run through the ASHEN pipeline, plus hand cleanup.

Sources live in tools/sprites/art/source/ (generated in Figma, file "ASHEN source art"). Each
sprite is pixelated by pipeline/pixelate.py at its native size, cleaned up here where the
pipeline loses something that matters (the eclipse's black, the Warden's crown, eyes and て
sigil, the atlas path on the map), then scaled up with NEAREST to the size the pages expect.

Usage:
  uv run --with pillow --with numpy --with scipy --with opencv-python-headless \\
      python tools/sprites/ronin.py src/hollow/adapters/web/static/sprites
"""

import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "src"))
import bonfire  # noqa: E402
from generated import SRC, cropped, glow, landmark_masks, pixelate, scaled, veil  # noqa: E402
from kit import BAYER4, Canvas, blend, hx, ramp  # noqa: E402
from waypoints import waypoints  # noqa: E402

from hollow.domain.atlas import RONIN_REGION_MAPS, REGIONS, WORLD_SIZE  # noqa: E402

def eclipse(c: Canvas, cx: float, cy: float, r: float) -> None:
    """The pipeline's value stretch lifts the eclipse's black to grey; put the void back."""
    d = np.hypot(c.xx - cx, c.yy - cy)
    c.fill(d <= r, hx("08050a"))
    c.fill((d > r) & (d <= r + 1.2), hx("fff0c0"))
    c.fill((d > r - 1.5) & (d <= r) & (c.yy > cy + r * 0.3) & ((c.xx + c.yy) % 2 == 0), hx("5a240c"))


REGION_ART: dict[str, tuple[str, tuple[int, int, int, int], tuple[float, float, float]]] = {
    # region: (source painting, crop to the map's 260x150 grid, eclipse centre and radius in 2x)
    "firelink": ("firelink.jpg", (19, 0, 1517, 864), (108, 36, 17.5)),
    "undead-village": ("undead_village.jpg", (19, 0, 1517, 864), (99, 32, 17.5)),
}


def firelink(tmp: Path) -> Image.Image:
    return region_map("firelink", tmp)


def region_map(region: str, tmp: Path) -> Image.Image:
    """A Ronin region map: the scene, with the atlas path laid over it."""
    nodes, size, _ = RONIN_REGION_MAPS[region]
    painting, crop, sun = REGION_ART[region]
    w, h = size[0] * 2, size[1] * 2
    src = cropped(SRC / painting, crop, tmp)
    c = Canvas(w, h)
    c.a = np.array(pixelate(src, tmp, "--preset", "landscape", "--width", str(w), "--colors", "64",
                            "--chroma", "1.1"))  # fmt: skip
    eclipse(c, *sun)
    pts = [(n.point[0] * 2, n.point[1] * 2) for n in nodes]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):  # ember motes along the way
        steps = int(max(abs(x1 - x0), abs(y1 - y0)))
        for i in range(4, steps - 3, 5):
            x = round(x0 + (x1 - x0) * i / steps)
            y = round(y0 + (y1 - y0) * i / steps) + 2
            c.dot(x, y + 1, blend(c.get(x, y + 1), hx("1a0f0a"), 0.6))
            c.dot(x, y, hx("ec9a2e") if i % 10 == 4 else hx("c46a1c"))
    stone = ramp("15110f", "221c19", "322a25", "463b33", "5e5046", "7b6b5c", "a08d78", "c8b49a")
    for x, y in pts[1:-1]:  # footing stones under each lesson
        top = c.ellipse((x - 9, y - 1, x + 9, y + 5))
        c.shade(top, stone, light=(-0.5, -1), soft=1.2, lo=0.25, hi=0.9)
        c.fill(c.ellipse((x - 9, y + 2, x + 9, y + 8)) & ~top, stone[1])
        c.rim(top, hx("e0b45a"), d=(0, -1))
    return scaled(c.img(), 2)


def world(tmp: Path) -> Image.Image:
    """The Ronin world map: six regions on one road, from the Firelink bonfire to the Kiln.

    The region points in atlas.REGIONS sit on the painted landmarks of this source."""
    w, h = WORLD_SIZE[0] * 2, WORLD_SIZE[1] * 2
    src = cropped(SRC / "world.jpg", (40, 0, 1223, 1024), tmp)
    c = Canvas(w, h)
    c.a = np.array(pixelate(src, tmp, "--preset", "landscape", "--width", str(w), "--colors", "64",
                            "--chroma", "1.1"))  # fmt: skip
    eclipse(c, 252.5, 30.5, 19.5)
    return scaled(c.img(), 2)


def arena(tmp: Path) -> Image.Image:
    src = cropped(SRC / "arena_firelink.jpg", (0, 40, 1536, 1000), tmp)
    c = Canvas(720, 450)
    c.a = np.array(pixelate(src, tmp, "--preset", "landscape", "--width", "720", "--colors", "64",
                            "--chroma", "1.1"))  # fmt: skip
    eclipse(c, 490, 23, 27.5)
    return scaled(c.img(), 2)


def landmarks(out: Path) -> None:
    """Hover outlines for the world map's regions and Firelink's bonfire and fog gate."""
    world = Image.open(out / "map_bg.png")
    masks = landmark_masks(SRC / "world.jpg", (40, 0, 1223, 1024), WORLD_SIZE,
                           {r.id: r.area for r in REGIONS if r.area})  # fmt: skip
    for key, m in masks.items():
        glow(world, m).save(out / f"spot_world_{key}.png")
        veil(world, m).save(out / f"veil_world_{key}.png")
    for region_id, (nodes, size, art) in RONIN_REGION_MAPS.items():
        region_landmarks(out, region_id)


def region_landmarks(out: Path, region_id: str) -> None:
    """Hover outlines for a Ronin region's bonfire and fog gate."""
    nodes, size, art = RONIN_REGION_MAPS[region_id]
    painting, crop, _ = REGION_ART[region_id]
    region = Image.open(out / art)
    masks = landmark_masks(SRC / painting, crop, size, {n.id: n.area for n in nodes if n.area})
    for key, m in masks.items():
        glow(region, m).save(out / f"spot_{region_id}_{key}.png")


# the て glyph, drawn at 2 px per cell on the Warden's shield
TE = ["############", "......##....", ".....##.....", "....##......", "....##......",
      "....##......", "....###.....", ".....######."]  # fmt: skip


def warden(tmp: Path) -> Image.Image:
    c = Canvas(136, 168)
    c.a = np.array(pixelate(SRC / "warden.jpg", tmp, "--preset", "boss", "--width", "136",
                            "--height", "168", "--colors", "24", "--smooth", "1.8", "--gamma", "0.7",
                            "--chroma", "1.3"))  # fmt: skip
    for x in range(58, 73):  # the crown: a gold band and spikes
        c.dot(x, 13, hx("b88c3c"))
        c.dot(x, 14, hx("7a5a24"))
    for x, h in ((58, 3), (61, 4), (64, 6), (65, 6), (68, 4), (71, 3)):
        for k in range(h):
            c.dot(x, 12 - k, hx("e0b45a") if k < h - 1 else hx("f6d98a"))
        c.dot(x + 1, 12, hx("5a4020"))
    for ex in (66, 69):  # two embers in the dark of the hood
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            c.dot(ex + dx, 17 + dy, hx("4a1016"))
        c.dot(ex, 17, hx("e8806a"))
    c.dot(66, 17, hx("ffd8b0"))
    ox, oy = 16, 66  # the burning て on the shield
    g = np.zeros((c.h, c.w), bool)
    for j, row in enumerate(TE):
        for i, ch in enumerate(row):
            if ch == "#":
                g[oy + j * 2 : oy + j * 2 + 2, ox + i * 2 : ox + i * 2 + 2] = True
    halo = np.zeros_like(g)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            halo |= np.roll(np.roll(g, dx, 1), dy, 0)
    c.fill(halo & ~g & ((c.xx + c.yy) % 2 == 0), hx("5a240c"))
    c.fill(halo & ~g & ((c.xx + c.yy) % 2 == 1), hx("8e3e12"))
    depth = (c.yy - oy) / (len(TE) * 2)
    c.fill(g & (depth < 0.35), hx("f6c55a"))
    c.fill(g & (depth >= 0.35) & (depth < 0.75), hx("ec9a2e"))
    c.fill(g & (depth >= 0.75), hx("c46a1c"))
    c.fill(g & ~np.roll(g, 1, 0), hx("fff0c0"))
    return scaled(c.img(), 3)


def knight(tmp: Path) -> Image.Image:
    """The hero, a hollow ronin: kasa hat, one ember eye, ragged haori, bandaged hands.

    The source faces left; mirrored, he faces right, toward the bosses in the arena. He holds
    nothing: weapons.py draws each weapon into his fist (weapons.HERO_GRIP)."""
    flipped = tmp / "hero.png"
    Image.open(SRC / "hero.jpg").convert("RGB").transpose(Image.Transpose.FLIP_LEFT_RIGHT).save(flipped)
    c = Canvas(77, 120)
    c.a = np.array(pixelate(flipped, tmp, "--preset", "character", "--width", "77", "--height", "120",
                            "--colors", "20", "--smooth", "1.8", "--gamma", "0.7", "--chroma", "1.3"))  # fmt: skip
    c.dot(32, 14, hx("ffd88a"))  # the last ember of him, under the hat
    c.dot(33, 14, hx("ec9a2e"))
    return scaled(c.img(), 2)


STAGE = (162, 146)
"""The bonfire stage on the home page: 324x292 CSS px, drawn at 2x."""
FIRE_AT = (121, 103)
"""Where the bonfire's flame sits on the stage, in stage pixels (matches .fire in the CSS)."""


def stage(tmp: Path) -> tuple[Image.Image, Image.Image]:
    """The shrine nook behind the knight: lit by the bonfire, and cold under the moon."""
    w, h = STAGE
    src = cropped(SRC / "stage.jpg", (0, 50, 1024, 973), tmp)
    base = np.array(pixelate(src, tmp, "--preset", "landscape", "--width", str(w), "--colors", "40",
                             "--gamma", "0.9", "--chroma", "1.1"))  # fmt: skip
    cold = Canvas(w, h)
    cold.a = base.copy()
    rgb = cold.a[..., :3].astype(float)
    cold.a[..., :3] = (rgb * np.array([0.82, 0.86, 1.0])).round().astype(np.uint8)
    lit = Canvas(w, h)
    lit.a = cold.a.copy()
    fx, fy = FIRE_AT
    d = np.hypot((lit.xx - fx) / 1.25, (lit.yy - fy) * 1.0)
    k = np.clip(1 - d / 92, 0, 1) ** 1.4
    q = np.floor(k * 6 + BAYER4[lit.yy % 4, lit.xx % 4] * 0.999) / 6
    rgb = lit.a[..., :3].astype(float)
    lum = rgb @ np.array([0.3, 0.59, 0.11]) / 255
    warm = np.array(hx("f4a040"), float)
    tint = warm * (0.3 + 1.2 * lum[..., None])
    out = rgb + (tint - rgb) * q[..., None] * 0.75
    lit.a[..., :3] = out.round().clip(0, 255).astype(np.uint8)
    return scaled(lit.img(), 2), scaled(cold.img(), 2)


def bonfire_art(tmp: Path) -> tuple[Image.Image, Image.Image]:
    """The lit 8-frame sheet and the cold, unlit bonfire."""
    base = pixelate(SRC / "bonfire.jpg", tmp, "--preset", "character", "--width", "72",
                    "--height", "90", "--colors", "24", "--palette", "auto", "--mode", "majority",
                    "--smooth", "1.8", "--gamma", "0.85", "--contrast", "0.03")  # fmt: skip
    return scaled(bonfire.sheet(base), 2), scaled(bonfire.unlit(base), 2)


if __name__ == "__main__":
    out = Path(sys.argv[1])
    if sys.argv[2:]:  # just the named regions' maps: ronin.py OUT undead-village
        with tempfile.TemporaryDirectory() as d:
            for region_id in sys.argv[2:]:
                region_map(region_id, Path(d)).save(out / RONIN_REGION_MAPS[region_id][2])
                region_landmarks(out, region_id)
        sys.exit(0)
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        lit, cold = bonfire_art(tmp)
        lit.save(out / "bonfire_sheet8.png")
        cold.save(out / "bonfire_unlit.png")
        stage_lit, stage_cold = stage(tmp)
        stage_lit.save(out / "stage_lit.png")
        stage_cold.save(out / "stage_unlit.png")
        knight(tmp).save(out / "knight_front.png")
        warden(tmp).save(out / "warden_body.png")
        for region_id, (_, _, art) in RONIN_REGION_MAPS.items():
            region_map(region_id, tmp).save(out / art)
        world(tmp).save(out / "map_bg.png")
        arena(tmp).save(out / "arena_bg.png")
    for name, img in waypoints().items():
        img.save(out / name)
    landmarks(out)
