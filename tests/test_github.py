from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest

from hollow.adapters.db.store import SqlEventStore
from hollow.adapters.github_api import PAGE_SIZE, GitHubApi
from hollow.application.github_sync import Checks, GitHubResult, GitHubSync, GitHubUnavailable
from hollow.domain.activities import ActivityKind
from hollow.domain.events import Source, StudyLogged
from hollow.domain.github import MergedPullRequest, to_event
from tests.conftest import FakeClock
from tests.test_anki import CAL

REPO = "MBigaj/hollow-trials"
GAME_START = datetime(2026, 10, 20, 2, tzinfo=UTC)  # 04:00 Warsaw on the first day


def pr(number: int, *, at: datetime, author: str = "MBigaj", repo: str = REPO) -> MergedPullRequest:
    return MergedPullRequest(
        repo=repo,
        number=number,
        title=f"Trial {number}",
        author=author,
        merged_at=at,
        head_sha=f"sha{number}",
    )


@dataclass
class FakeGitHub:
    pulls: list[MergedPullRequest] = field(default_factory=list)
    results: dict[str, Checks] = field(default_factory=dict)
    asked_since: list[datetime] = field(default_factory=list)
    down: bool = False

    def merged_pull_requests(self, repo: str, since: datetime) -> list[MergedPullRequest]:
        if self.down:
            raise GitHubUnavailable("Could not reach GitHub")
        self.asked_since.append(since)
        return [p for p in self.pulls if p.repo == repo and p.merged_at > since]

    def checks(self, repo: str, sha: str) -> Checks:
        return self.results.get(sha, Checks.PASSED)


def make_sync(store: SqlEventStore, clock: FakeClock, github: FakeGitHub) -> GitHubSync:
    return GitHubSync(store, github, clock, CAL, (REPO,), "mbigaj")


# --- mapping ------------------------------------------------------------------


def test_a_merged_pull_request_is_one_pr_activity() -> None:
    at = datetime(2026, 10, 20, 10, tzinfo=UTC)
    event = to_event(pr(7, at=at))
    assert event.kind is ActivityKind.PULL_REQUEST
    assert event.quantity == 1
    assert event.source is Source.GITHUB
    assert event.occurred_at == at
    assert event.note == f"{REPO}#7 Trial 7"
    assert event.id == to_event(pr(7, at=at + timedelta(hours=1), repo=REPO.lower())).id


# --- sync use case ------------------------------------------------------------


def test_only_my_passing_prs_since_the_game_began_count(
    store: SqlEventStore, clock: FakeClock
) -> None:
    now = clock.now()
    github = FakeGitHub(
        [
            pr(1, at=now - timedelta(hours=1)),
            pr(2, at=now - timedelta(hours=2), author="someone-else"),
            pr(3, at=now - timedelta(days=30)),
            pr(4, at=now - timedelta(hours=3)),
            pr(5, at=now - timedelta(hours=4)),
            pr(6, at=now - timedelta(hours=5)),
        ],
        results={"sha4": Checks.FAILED, "sha5": Checks.RUNNING, "sha6": Checks.NONE},
    )

    result = make_sync(store, clock, github).run()

    assert result == GitHubResult(merged=1, waiting=1)
    assert github.asked_since == [GAME_START]
    [event] = store.all()
    assert isinstance(event, StudyLogged) and event.note.startswith(f"{REPO}#1 ")


def test_a_pr_waiting_for_ci_counts_once_ci_passes(store: SqlEventStore, clock: FakeClock) -> None:
    github = FakeGitHub([pr(1, at=clock.now())], results={"sha1": Checks.RUNNING})
    sync = make_sync(store, clock, github)
    assert sync.run() == GitHubResult(merged=0, waiting=1)

    github.results["sha1"] = Checks.PASSED
    assert sync.run(force=True) == GitHubResult(merged=1, waiting=0)
    assert sync.run(force=True) == GitHubResult(merged=0, waiting=0)
    assert len(store.all()) == 1


def test_page_loads_are_throttled_but_forced_runs_are_not(
    store: SqlEventStore, clock: FakeClock
) -> None:
    github = FakeGitHub()
    sync = make_sync(store, clock, github)
    assert sync.run() is not None
    assert sync.run() is None
    assert sync.run(force=True) is not None
    clock.advance(hours=1)
    assert sync.run() is not None
    assert len(github.asked_since) == 3


def test_github_errors_surface_to_the_caller(store: SqlEventStore, clock: FakeClock) -> None:
    with pytest.raises(GitHubUnavailable):
        make_sync(store, clock, FakeGitHub(down=True)).run()


# --- REST adapter -------------------------------------------------------------


def iso(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def pull(number: int, *, merged: datetime | None, updated: datetime) -> dict[str, Any]:
    return {
        "number": number,
        "title": f"Trial {number}",
        "user": {"login": "MBigaj"},
        "merged_at": iso(merged) if merged else None,
        "updated_at": iso(updated),
        "head": {"sha": f"sha{number}"},
    }


def github_server(
    pages: list[list[dict[str, Any]]],
    runs: list[dict[str, Any]] | None = None,
    statuses: list[dict[str, Any]] | None = None,
    requests: list[httpx.Request] | None = None,
) -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        if requests is not None:
            requests.append(request)
        path = request.url.path
        if path.endswith("/pulls"):
            page = int(request.url.params["page"])
            return httpx.Response(200, json=pages[page - 1] if page <= len(pages) else [])
        if path.endswith("/check-runs"):
            return httpx.Response(200, json={"check_runs": runs or []})
        if path.endswith("/status"):
            return httpx.Response(200, json={"statuses": statuses or []})
        return httpx.Response(404)

    return httpx.MockTransport(handle)


def test_adapter_reads_merged_prs_and_stops_paging_at_old_updates() -> None:
    since = datetime(2026, 10, 20, tzinfo=UTC)
    recent = since + timedelta(hours=5)
    old = since - timedelta(days=3)
    first = [pull(10, merged=recent, updated=recent), pull(9, merged=None, updated=recent)]
    first += [pull(100 + n, merged=old, updated=recent) for n in range(PAGE_SIZE - 3)]
    first.append(pull(8, merged=old, updated=old))
    requests: list[httpx.Request] = []
    api = GitHubApi(token="secret", transport=github_server([first, first], requests=requests))

    found = api.merged_pull_requests(REPO, since)

    assert [p.number for p in found] == [10]
    assert found[0] == MergedPullRequest(REPO, 10, "Trial 10", "MBigaj", recent, "sha10")
    assert len(requests) == 1  # the last pull on page 1 was updated before `since`
    assert requests[0].headers["Authorization"] == "Bearer secret"
    assert requests[0].url.params["state"] == "closed"


def test_adapter_follows_pages_while_updates_are_recent() -> None:
    since = datetime(2026, 10, 20, tzinfo=UTC)
    recent = since + timedelta(hours=1)
    full = [pull(n, merged=recent, updated=recent) for n in range(PAGE_SIZE)]
    api = GitHubApi(transport=github_server([full, [pull(999, merged=recent, updated=recent)]]))
    assert len(api.merged_pull_requests(REPO, since)) == PAGE_SIZE + 1


def run(status: str = "completed", conclusion: str | None = "success") -> dict[str, Any]:
    return {"status": status, "conclusion": conclusion}


@pytest.mark.parametrize(
    ("runs", "statuses", "expected"),
    [
        ([], [], Checks.NONE),
        ([run(), run(conclusion="skipped")], [], Checks.PASSED),
        ([], [{"state": "success"}], Checks.PASSED),
        ([run(), run(status="in_progress", conclusion=None)], [], Checks.RUNNING),
        ([run()], [{"state": "pending"}], Checks.RUNNING),
        ([run(), run(conclusion="failure")], [], Checks.FAILED),
        ([run()], [{"state": "error"}], Checks.FAILED),
    ],
)
def test_adapter_combines_check_runs_and_statuses(
    runs: list[dict[str, Any]], statuses: list[dict[str, Any]], expected: Checks
) -> None:
    api = GitHubApi(transport=github_server([], runs=runs, statuses=statuses))
    assert api.checks(REPO, "sha1") is expected


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (httpx.Response(401), "refused"),
        (httpx.Response(403), "refused"),
        (httpx.Response(404), "could not find MBigaj/hollow-trials"),
        (httpx.Response(500), "unexpected"),
        (httpx.Response(200, content=b"not json"), "unexpected"),
    ],
)
def test_adapter_reports_github_problems(response: httpx.Response, message: str) -> None:
    api = GitHubApi(transport=httpx.MockTransport(lambda request: response))
    with pytest.raises(GitHubUnavailable, match=message):
        api.merged_pull_requests(REPO, GAME_START)


def test_adapter_reports_an_unreachable_github() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no network", request=request)

    with pytest.raises(GitHubUnavailable, match="Could not reach"):
        GitHubApi(transport=httpx.MockTransport(refuse)).checks(REPO, "sha1")
