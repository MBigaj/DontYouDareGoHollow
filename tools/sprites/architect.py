"""The Architect road's art: generated paintings run through the ASHEN pipeline, like ronin.py.

Sources live in art/source/ (prompts in PROMPTS.md): the world map, the Forge, Data Depths,
the Strict Golem, the Lock Wyrm and their arenas. This road is cold: night blue, steel and
soul cyan, with the violet of the Distributed Abyss in the sky (Dark Souls leaning; the Ronin
road is golden dusk). The pipeline runs darker here (gamma above 1) so night stays night.
Hand cleanup restores the Golem's visor and the Wyrm's eye, and the region maps get a trail of
cyan motes along their atlas paths. The waypoints are the grave stones every map shares
(waypoints.py, built by ronin.py); the weapons, the Lock Wyrm's Chain among them, are in weapons.py.

Usage:
  uv run --with pillow --with numpy --with scipy --with opencv-python-headless \\
      python tools/sprites/architect.py src/hollow/adapters/web/static/sprites
"""

import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent.parent / "src"))
from generated import (  # noqa: E402
    CYAN,
    NIGHT_FOG,
    SRC,
    cropped,
    glow,
    landmark_masks,
    pixelate,
    scaled,
    veil,
)
from kit import STEEL, Canvas, blend, hx, ramp  # noqa: E402

from hollow.domain.atlas import (  # noqa: E402
    ARCH_AREAS,
    ARCH_WORLD_SIZE,
    DEPTHS,
    DEPTHS_SIZE,
    FORGE,
    FORGE_SIZE,
    Node,
)

NIGHT = ("--colors", "64", "--gamma", "1.15", "--smooth", "0.6", "--sharpen", "1.2",
         "--chroma", "1.2")  # fmt: skip
"""Outdoor night scenes: darker mid-tones than the Ronin road's dusk."""
VAULT = ("--colors", "72", "--gamma", "1.1", "--smooth", "0.3", "--sharpen", "1.6",
         "--chroma", "1.25")  # fmt: skip
"""Dark interiors: less smoothing and more sharpening, so shelves and edges survive."""
BOSS = ("--preset", "boss", "--colors", "28", "--smooth", "1.2", "--gamma", "0.85",
        "--chroma", "1.25", "--sharpen", "1.3")  # fmt: skip

WORLD_CROP = (20, 0, 1203, 1024)
REGION_CROP = (19, 0, 1517, 864)
ARENA_CROP = (0, 40, 1536, 1000)


def world(tmp: Path) -> Image.Image:
    """Eight regions on one road, under the abyss. atlas.ARCH_POINTS sit on the landmarks."""
    w = ARCH_WORLD_SIZE[0] * 2
    src = cropped(SRC / "architect_world.jpg", WORLD_CROP, tmp)
    return scaled(pixelate(src, tmp, "--preset", "landscape", "--width", str(w), *NIGHT), 2)


def region(tmp: Path, name: str, nodes: tuple[Node, ...], size: tuple[int, int]) -> Image.Image:
    """A region map, with soul-cyan motes along the atlas path to guide the eye."""
    w, h = size[0] * 2, size[1] * 2
    src = cropped(SRC / f"{name}.jpg", REGION_CROP, tmp)
    c = Canvas(w, h)
    c.a = np.array(pixelate(src, tmp, "--preset", "landscape", "--width", str(w), *VAULT))
    pts = [(n.point[0] * 2, n.point[1] * 2) for n in nodes]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:], strict=False):
        steps = int(max(abs(x1 - x0), abs(y1 - y0)))
        for i in range(4, steps - 3, 5):
            x = round(x0 + (x1 - x0) * i / steps)
            y = round(y0 + (y1 - y0) * i / steps) + 2
            c.dot(x, y + 1, blend(c.get(x, y + 1), hx("05080c"), 0.6))
            c.dot(x, y, hx("9ee2ee") if i % 10 == 4 else hx("4fb4d0"))
    return scaled(c.img(), 2)


def golem(tmp: Path) -> Image.Image:
    c = Canvas(144, 168)
    c.a = np.array(pixelate(SRC / "golem.jpg", tmp, *BOSS, "--width", "144", "--height", "168"))
    for x in range(69, 75):  # the visor slit, burning cold
        c.dot(x, 9, hx("e6fbff") if 70 <= x <= 73 else hx("9ee2ee"))
    return scaled(c.img(), 3)


def wyrm(tmp: Path) -> Image.Image:
    c = Canvas(160, 168)
    c.a = np.array(pixelate(SRC / "wyrm.jpg", tmp, *BOSS, "--width", "160", "--height", "168"))
    for (x, y), col in (((48, 23), "4fb4d0"), ((49, 23), "e6fbff"), ((50, 23), "9ee2ee"),
                        ((49, 24), "4fb4d0")):  # fmt: skip
        c.dot(x, y, hx(col))  # the eye
    return scaled(c.img(), 3)


def arena(tmp: Path, name: str) -> Image.Image:
    src = cropped(SRC / f"{name}.jpg", ARENA_CROP, tmp)
    return scaled(pixelate(src, tmp, "--preset", "landscape", "--width", "720", *VAULT), 2)


def landmarks(out: Path) -> None:
    """Hover glows (cyan on this road) and fog veils for the regions; the region maps' bonfires
    and boss gates."""
    art = Image.open(out / "map_architect.png")
    masks = landmark_masks(SRC / "architect_world.jpg", WORLD_CROP, ARCH_WORLD_SIZE, ARCH_AREAS)
    for key, m in masks.items():
        glow(art, m, CYAN).save(out / f"spot_architect_{key}.png")
        if key == "distributed-abyss":  # the road's goal looms in the sky from the start
            m = np.zeros_like(m)
        veil(art, m, NIGHT_FOG).save(out / f"veil_architect_{key}.png")
    for map_id, name, nodes, size, file in (
        ("forge", "forge", FORGE, FORGE_SIZE, "region_forge.png"),
        ("data-depths", "data_depths", DEPTHS, DEPTHS_SIZE, "region_data_depths.png"),
    ):
        art = Image.open(out / file)
        masks = landmark_masks(SRC / f"{name}.jpg", REGION_CROP, size,
                               {n.id: n.area for n in nodes if n.area})  # fmt: skip
        for key, m in masks.items():
            glow(art, m, CYAN).save(out / f"spot_{map_id}_{key}.png")


if __name__ == "__main__":
    out = Path(sys.argv[1])
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        world(tmp).save(out / "map_architect.png")
        region(tmp, "forge", FORGE, FORGE_SIZE).save(out / "region_forge.png")
        region(tmp, "data_depths", DEPTHS, DEPTHS_SIZE).save(out / "region_data_depths.png")
        golem(tmp).save(out / "golem_body.png")
        wyrm(tmp).save(out / "wyrm_body.png")
        arena(tmp, "arena_forge").save(out / "arena_forge.png")
        arena(tmp, "arena_data_depths").save(out / "arena_data_depths.png")
    landmarks(out)
