import re
from datetime import timedelta

from fastapi.testclient import TestClient

from hollow.adapters.db.store import SqlEventStore
from hollow.domain.atlas import FIRELINK, FIRELINK_SIZE, REGIONS
from hollow.domain.events import LessonCompleted
from tests.conftest import FakeClock
from tests.test_web_lessons import learn


def node_class(page: str, node: str) -> str:
    match = re.search(rf'<a class="node ([^"]*)" href="\?at={node}"', page)
    assert match, node
    return str(match.group(1)).strip()


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
