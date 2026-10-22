from collections.abc import Iterator
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from hollow.adapters.db.store import SqlEventStore
from hollow.adapters.web.app import create_app
from hollow.config import Settings
from tests.conftest import FakeClock
from tests.test_anki import FakeAnki, first_sight, review

HX = {"HX-Request": "true"}


@pytest.fixture
def anki() -> FakeAnki:
    return FakeAnki()


@pytest.fixture
def anki_client(store: SqlEventStore, clock: FakeClock, anki: FakeAnki) -> Iterator[TestClient]:
    settings = Settings(database_url="sqlite://", _env_file=None)
    with TestClient(create_app(settings, store=store, clock=clock, anki=anki)) as client:
        yield client


def test_opening_the_page_syncs_anki(
    anki_client: TestClient, anki: FakeAnki, clock: FakeClock
) -> None:
    anki.reviews = [review(clock.now() - timedelta(seconds=n), card=n) for n in range(10)]
    assert anki.asked_after == []  # the page itself never waits for Anki
    assert 'hx-post="/sync?page=bonfire"' in anki_client.get("/").text
    page = anki_client.post("/sync", headers=HX).text
    assert "From Anki: 10 reviews, 0 new cards. The bonfire is lit." in page
    assert "Anki reviews: 10 reviews" in page


def test_anki_activities_leave_the_manual_form(anki_client: TestClient) -> None:
    page = anki_client.get("/").text
    assert 'value="anki_reviews"' not in page
    assert 'value="grammar_drill"' in page
    assert "Do 10 reviews in Anki, then press to sync" in page


def test_light_syncs_and_explains_what_is_missing(
    anki_client: TestClient, anki: FakeAnki, clock: FakeClock
) -> None:
    anki.reviews = [first_sight(clock.now())]
    text = anki_client.post("/light", headers=HX).text
    assert "From Anki: 0 reviews, 1 new cards." in text
    assert "10 reviews or 5 new cards today will light it." in text

    text = anki_client.post("/light", headers=HX).text
    assert "No new Anki reviews." in text


def test_closed_anki_shows_a_warning_not_an_error(anki_client: TestClient, anki: FakeAnki) -> None:
    anki.down = True
    page = anki_client.post("/sync", headers=HX)
    assert page.status_code == 200
    assert "Anki is not reachable" in page.text
    assert "Anki is not reachable" in anki_client.post("/light", headers=HX).text


def test_settings_turn_on_anki_connect() -> None:
    settings = Settings(anki_enabled=True, anki_decks=" Core 2000, Kanji ,", _env_file=None)
    assert settings.anki_deck_names() == ("Core 2000", "Kanji")
    app = create_app(settings, store=None)
    assert app.title == "DontYouDareGoHollow"


def test_a_sync_with_nothing_new_redraws_nothing(anki_client: TestClient) -> None:
    response = anki_client.post("/sync", headers=HX)
    assert response.status_code == 204
    assert response.text == ""


def test_the_character_page_syncs_into_its_own_panel(
    anki_client: TestClient, anki: FakeAnki, clock: FakeClock
) -> None:
    assert 'hx-post="/sync?page=character"' in anki_client.get("/character").text
    anki.reviews = [first_sight(clock.now())]
    text = anki_client.post("/sync?page=character", headers=HX).text
    assert 'id="character"' in text
    assert "From Anki: 0 reviews, 1 new cards." in text
