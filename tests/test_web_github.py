from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from hollow.adapters.db.store import SqlEventStore
from hollow.adapters.web.app import create_app
from hollow.application.github_sync import Checks
from hollow.config import Settings
from tests.conftest import FakeClock
from tests.test_anki import FakeAnki
from tests.test_github import FakeGitHub, pr

HX = {"HX-Request": "true"}


@pytest.fixture
def github() -> FakeGitHub:
    return FakeGitHub()


@pytest.fixture
def github_client(
    store: SqlEventStore, clock: FakeClock, github: FakeGitHub
) -> Iterator[TestClient]:
    settings = Settings(database_url="sqlite://", _env_file=None)
    with TestClient(create_app(settings, store=store, clock=clock, github=github)) as client:
        yield client


def test_a_merged_pr_lights_the_bonfire(
    github_client: TestClient, github: FakeGitHub, clock: FakeClock
) -> None:
    github.pulls = [pr(1, at=clock.now())]
    page = github_client.get("/").text
    assert "From GitHub: 1 merged PR. The bonfire is lit." in page


def test_prs_leave_the_manual_form(github_client: TestClient) -> None:
    page = github_client.get("/").text
    assert 'value="pull_request"' not in page
    assert 'value="dev_study"' in page


def test_light_reports_prs_waiting_for_ci(
    github_client: TestClient, github: FakeGitHub, clock: FakeClock
) -> None:
    github.pulls = [pr(1, at=clock.now()), pr(2, at=clock.now())]
    github.results = {"sha1": Checks.RUNNING, "sha2": Checks.RUNNING}
    text = github_client.post("/light", headers=HX).text
    assert "2 merged PRs still waiting for CI." in text

    github.results = {}
    text = github_client.post("/light", headers=HX).text
    assert "From GitHub: 2 merged PRs. The bonfire is lit." in text


def test_github_problems_show_a_warning(github_client: TestClient, github: FakeGitHub) -> None:
    github.down = True
    page = github_client.get("/")
    assert page.status_code == 200
    assert "GitHub sync failed: Could not reach GitHub." in page.text


def test_both_syncs_report_together(
    store: SqlEventStore, clock: FakeClock, github: FakeGitHub
) -> None:
    github.pulls = [pr(1, at=clock.now())]
    anki = FakeAnki(down=True)
    settings = Settings(database_url="sqlite://", _env_file=None)
    app = create_app(settings, store=store, clock=clock, anki=anki, github=github)
    with TestClient(app) as client:
        text = client.post("/light", headers=HX).text
    assert "From GitHub: 1 merged PR. The bonfire is lit." in text
    assert "Anki is not reachable" in text


def test_settings_build_the_real_client(
    store: SqlEventStore, clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    built: list[str | None] = []

    class Recorder(FakeGitHub):
        def __init__(self, token: str | None = None) -> None:
            super().__init__()
            built.append(token)

    monkeypatch.setattr("hollow.adapters.web.app.GitHubApi", Recorder)
    settings = Settings(
        database_url="sqlite://", github_enabled=True, github_token="t0ken", _env_file=None
    )
    with TestClient(create_app(settings, store=store, clock=clock)) as client:
        assert client.get("/").status_code == 200
    assert built == ["t0ken"]
    assert settings.github_repo_names() == ("MBigaj/hollow-trials",)


def test_page_loads_check_github_at_most_every_few_minutes(
    github_client: TestClient, github: FakeGitHub
) -> None:
    github_client.get("/")
    github_client.get("/")
    assert len(github.asked_since) == 1
