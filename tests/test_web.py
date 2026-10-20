from fastapi.testclient import TestClient
from pydantic import SecretStr

from hollow.adapters.db.store import SqlEventStore
from hollow.adapters.web.app import create_app
from hollow.config import Settings
from tests.conftest import FakeClock

HX = {"HX-Request": "true"}


def test_home_shows_an_unlit_bonfire(client: TestClient) -> None:
    page = client.get("/")
    assert page.status_code == 200
    assert "LIGHT THE BONFIRE" in page.text
    assert "Nothing logged yet today." in page.text


def test_light_returns_the_world_partial_for_htmx(client: TestClient) -> None:
    response = client.post("/light", headers=HX)
    assert response.status_code == 200
    assert response.text.lstrip().startswith('<div id="world"')
    assert "The bonfire is lit." in response.text
    assert "LIGHT THE BONFIRE" not in response.text


def test_forms_work_without_javascript(client: TestClient) -> None:
    response = client.post("/light", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert "The bonfire is lit for today." in client.get("/").text


def test_log_study_adds_souls(client: TestClient) -> None:
    response = client.post(
        "/log", data={"kind": "dev_study", "quantity": "30", "note": "outbox"}, headers=HX
    )
    assert response.status_code == 200
    assert "Logged 30 minutes of Dev study." in response.text
    assert "Dev study: 30 minutes" in response.text


def test_log_rejects_bad_input(client: TestClient) -> None:
    assert client.post("/log", data={"kind": "nope", "quantity": "5"}).status_code == 422
    assert client.post("/log", data={"kind": "dev_study", "quantity": "0"}).status_code == 422


def test_missed_day_shows_bloodstain_then_recovery(client: TestClient, clock: FakeClock) -> None:
    client.post("/light")
    clock.advance(days=2)
    page = client.get("/").text
    assert "Bloodstain · 20 souls" in page

    recovered = client.post("/light", headers=HX).text
    assert "Bloodstain" not in recovered


def test_message_shows_the_next_day(client: TestClient, clock: FakeClock) -> None:
    response = client.post("/message", data={"text": "Try て-form ahead"}, headers=HX)
    assert response.status_code == 200
    assert "left by past you" not in response.text
    clock.advance(days=1)
    assert "Try て-form ahead" in client.get("/").text


def test_empty_message_is_rejected(client: TestClient) -> None:
    assert client.post("/message", data={"text": "   "}).status_code == 422


def test_healthz(client: TestClient) -> None:
    assert client.get("/healthz").json() == {"status": "ok"}


def test_password_protects_every_page(store: SqlEventStore, clock: FakeClock) -> None:
    settings = Settings(database_url="sqlite://", password=SecretStr("estus"), _env_file=None)
    client = TestClient(create_app(settings, store=store, clock=clock))
    assert client.get("/").status_code == 401
    assert client.get("/", auth=("me", "wrong")).status_code == 401
    assert client.get("/", auth=("me", "estus")).status_code == 200
