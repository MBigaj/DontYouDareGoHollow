import re
from datetime import timedelta

from fastapi.testclient import TestClient

from hollow.adapters.db.store import SqlEventStore
from hollow.domain.atlas import (
    ARCH_AREAS,
    ARCH_POINTS,
    ARCH_REGION_MAPS,
    FIRELINK,
    FIRELINK_SIZE,
    REGIONS,
    NodeKind,
)
from hollow.domain.events import LessonCompleted
from tests.conftest import FakeClock
from tests.test_web_lessons import learn


def node_class(page: str, node: str) -> str:
    match = re.search(rf'<a class="node ([^"]*)" href="\?at={node}"', page)
    assert match, node
    side = {"east", "west"}  # which way the label opens; layout, not progress
    return " ".join(c for c in str(match.group(1)).split() if c not in side)


def visible_panel(page: str) -> str:
    panels = re.findall(r'data-panel="([\w-]+)" (hidden)?', page)
    shown = [p for p, hidden in panels if not hidden]
    assert len(shown) == 1
    return str(shown[0])


def test_world_map_opens_firelink_and_fogs_the_rest(client: TestClient) -> None:
    page = client.get("/map").text
    assert 'href="/map" aria-current="page"' in page
    assert "fog" not in node_class(page, "firelink")
    for region in REGIONS[1:]:
        assert "fog" in node_class(page, region.id)
    assert 'href="/map/firelink" data-action>Enter Firelink Shrine' in page
    assert visible_panel(page) == "firelink"
    assert visible_panel(client.get("/map?at=the-kiln").text) == "the-kiln"


def test_firelink_shows_every_point_in_walking_order(
    client: TestClient, store: SqlEventStore, clock: FakeClock
) -> None:
    learn(store, clock)
    page = client.get("/map/firelink").text
    order = re.findall(r'data-node="([\w-]+)"', page)
    assert order == [n.id for n in FIRELINK]
    assert node_class(page, "te-ru") == "lesson new"
    assert node_class(page, "warden") == "boss due"
    assert 'href="/boss/te-warden" data-action>Enter the fog' in page
    assert 'href="/lessons/te-ru" data-action>Start' in page
    assert visible_panel(page) == "bonfire"
    x = 100 * FIRELINK[0].point[0] / FIRELINK_SIZE[0]
    assert f'data-x="{round(x, 2)}"' in page


def test_points_show_progress(client: TestClient, store: SqlEventStore, clock: FakeClock) -> None:
    learn(store, clock)
    store.append(LessonCompleted(clock.now(), "te-ru", 10, 10))
    store.append(LessonCompleted(clock.now() - timedelta(days=2), "te-tsu", 10, 10))
    page = client.get("/map/firelink").text
    assert node_class(page, "te-ru") == "lesson cleared"
    assert node_class(page, "te-tsu") == "lesson due"
    assert "29% explored" in page
    assert "Practise" in page and "Refresh" in page


def test_locked_lessons_are_unavailable(client: TestClient) -> None:
    page = client.get("/map/firelink?at=te-nde").text
    assert "locked" in node_class(page, "te-nde")
    assert visible_panel(page) == "te-nde"
    assert "Unavailable: learn 2 more verbs" in page
    assert "fog" in node_class(page, "warden")
    assert "It will not part until you know 6 verbs." in page


def test_the_knight_starts_where_you_left_it(client: TestClient) -> None:
    client.cookies.set("hollow_at_firelink", "te-mixed")
    page = client.get("/map/firelink").text
    assert 'data-at="te-mixed"' in page
    client.cookies.set("hollow_at_firelink", "nowhere")
    assert 'data-at="bonfire"' in client.get("/map/firelink").text
    client.cookies.set("hollow_at_world", "nowhere")
    assert 'data-at="firelink"' in client.get("/map").text


def inside(point: tuple[int, int], area: tuple[tuple[int, int], ...]) -> bool:
    """Ray casting: is the point inside the polygon?"""
    x, y = point
    hit = False
    for (x0, y0), (x1, y1) in zip(area, area[1:] + area[:1], strict=True):
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            hit = not hit
    return hit


def test_landmarks_hold_their_places() -> None:
    painted = [(r.id, r.point, r.area) for r in REGIONS] + [
        (n.id, n.point, n.area) for n in FIRELINK if n.area
    ]
    assert {p for p, _, _ in painted} >= {"bonfire", "warden"}
    for place, point, area in painted:
        assert len(area) >= 3, place
        assert inside(point, area), place  # the knight stands on the landmark


def test_world_regions_are_their_landmarks(client: TestClient) -> None:
    page = client.get("/map").text
    for region in REGIONS:
        status = "open" if region.open else "fog"
        points = " ".join(f"{x},{y}" for x, y in region.area)
        spot = re.search(
            rf'<a class="spot {status}" href="\?at={region.id}" data-spot="{region.id}" '
            rf'tabindex="-1">(.*?)</a>',
            page,
            re.S,
        )
        assert spot, region.id
        assert f"sprites/spot_world_{region.id}.png" in spot.group(1)
        assert f"sprites/veil_world_{region.id}.png" in spot.group(1)
        assert f'<polygon points="{points}"/>' in spot.group(1)
        assert re.search(rf'data-node="{region.id}"[^>]*data-landmark', page)


def test_firelink_bonfire_and_gate_are_landmarks(client: TestClient) -> None:
    page = client.get("/map/firelink").text
    assert re.findall(r'data-spot="([\w-]+)"', page) == ["bonfire", "warden"]
    assert "veil_firelink" not in page
    assert "spot_firelink_warden.png" in page
    assert not re.search(r'data-node="te-ru"[^>]*data-landmark', page)  # stones stay stones


def test_architect_landmarks_hold_their_places() -> None:
    assert set(ARCH_AREAS) == set(ARCH_POINTS)
    for region, area in ARCH_AREAS.items():
        assert inside(ARCH_POINTS[region], area), region
    for nodes, _, _ in ARCH_REGION_MAPS.values():
        painted = [n for n in nodes if n.area]
        assert [n.kind for n in painted] == [NodeKind.BONFIRE, NodeKind.BOSS]
        for node in painted:
            assert inside(node.point, node.area), node.id


def test_architect_regions_are_their_landmarks(client: TestClient) -> None:
    page = client.get("/map?road=architect").text
    spots = re.findall(r'<a class="spot (\w+)" href="\?at=([\w-]+)" data-spot', page)
    assert [s for _, s in spots] == list(ARCH_POINTS)
    assert dict((s, status) for status, s in spots)["forge"] == "open"
    assert "spot_architect_watchtower.png" in page and "veil_architect_watchtower.png" in page
