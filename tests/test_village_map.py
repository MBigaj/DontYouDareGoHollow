"""Undead Village, part 2: its map, opened when the て-form Warden falls."""

import struct
from pathlib import Path

from fastapi.testclient import TestClient

from hollow.adapters.db.store import SqlEventStore
from hollow.domain.atlas import RONIN_REGION_MAPS, VILLAGE, VILLAGE_SIZE, NodeKind
from hollow.domain.lessons import LESSONS
from tests.conftest import FakeClock
from tests.test_armory import fell_the_warden
from tests.test_web_lessons import learn

SPRITES = Path(__file__).parent.parent / "src/hollow/adapters/web/static/sprites"


def size(name: str) -> tuple[int, int]:
    width, height = struct.unpack(">II", (SPRITES / name).read_bytes()[16:24])  # the PNG header
    return width, height


def test_every_village_lesson_has_a_stone_on_the_street() -> None:
    kinds = [n.kind for n in VILLAGE]
    assert kinds[0] is NodeKind.BONFIRE and kinds[-1] is NodeKind.BOSS
    placed = [n.lesson_id for n in VILLAGE if n.kind is NodeKind.LESSON]
    assert placed == [s.id for s in LESSONS.values() if s.region == "undead-village"]
    w, h = VILLAGE_SIZE
    assert all(0 <= n.point[0] <= w and 0 <= n.point[1] <= h for n in VILLAGE)
    assert [n.point[0] for n in VILLAGE] == sorted(n.point[0] for n in VILLAGE)  # up the hill


def test_the_village_has_its_art() -> None:
    assert set(RONIN_REGION_MAPS) == {"firelink", "undead-village"}
    assert size("region_undead_village.png") == (VILLAGE_SIZE[0] * 4, VILLAGE_SIZE[1] * 4)
    for place in ("bonfire", "gargoyle"):
        assert size(f"spot_undead-village_{place}.png") == size("region_undead_village.png")


def test_the_village_waits_in_the_fog_until_the_warden_falls(
    client: TestClient, store: SqlEventStore, clock: FakeClock
) -> None:
    learn(store, clock)
    world = client.get("/map?road=ronin").text
    assert 'href="/map/undead-village"' not in world
    assert "opens after the boss before it falls: the て-form Warden" in world
    assert client.get("/map/undead-village").status_code == 404
    fell_the_warden(store, clock)
    world = client.get("/map?road=ronin").text
    assert 'href="/map/undead-village" data-action>Enter Undead Village' in world
    page = client.get("/map/undead-village").text
    assert "Region 2 · Undead Village · 0% explored" in page
    assert "region_undead_village.png" in page and "spot_undead-village_gargoyle.png" in page
    assert page.count('href="/lessons/pf-') == 6
    assert "Lesson 1 · plain forms" in page and "has not woken yet" in page
    assert client.get("/map/firelink").status_code == 200


def test_unknown_regions_are_not_found(client: TestClient) -> None:
    assert client.get("/map/kanji-catacombs").status_code == 404
    assert client.get("/map/nowhere").status_code == 404
