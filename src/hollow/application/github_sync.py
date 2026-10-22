"""Pulls merged pull requests from GitHub into the event log.

Only pull requests that you authored, in the configured repos, merged after the game began,
with CI that passed, count. Commits never count on their own: splitting work into tiny
commits would farm souls.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Protocol

from hollow.application.history import game_start
from hollow.application.ports import Clock, EventStore
from hollow.domain.calendar import GameCalendar
from hollow.domain.events import Source, StudyLogged
from hollow.domain.github import MergedPullRequest, to_event


class GitHubUnavailable(Exception):
    """GitHub could not be reached, refused the token, or hit its rate limit."""


class Checks(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    RUNNING = "running"
    NONE = "none"


class GitHubSource(Protocol):
    def merged_pull_requests(self, repo: str, since: datetime) -> list[MergedPullRequest]:
        """Pull requests in `repo` merged after `since`, newest first."""
        ...

    def checks(self, repo: str, sha: str) -> Checks:
        """The combined result of the CI runs on a commit."""
        ...


@dataclass(frozen=True)
class GitHubResult:
    merged: int
    waiting: int
    """Merged pull requests whose CI is still running; a later sync picks them up."""


MIN_INTERVAL = timedelta(minutes=5)
"""Page loads sync at most this often, to stay well inside GitHub's rate limits."""


class GitHubSync:
    def __init__(
        self,
        store: EventStore,
        source: GitHubSource,
        clock: Clock,
        calendar: GameCalendar,
        repos: tuple[str, ...],
        author: str,
    ) -> None:
        self._store = store
        self._source = source
        self._clock = clock
        self._calendar = calendar
        self._repos = repos
        self._author = author.lower()
        self._last_run: datetime | None = None

    def run(self, force: bool = False) -> GitHubResult | None:
        """Imports newly merged pull requests. Returns None when skipped by the throttle."""
        now = self._clock.now()
        if not force and self._last_run and now - self._last_run < MIN_INTERVAL:
            return None
        self._last_run = now

        since = game_start(self._store, self._clock, self._calendar)
        imported = {
            e.id
            for e in self._store.all()
            if isinstance(e, StudyLogged) and e.source is Source.GITHUB
        }
        ready: list[StudyLogged] = []
        waiting = 0
        for repo in self._repos:
            for pr in self._source.merged_pull_requests(repo, since):
                event = to_event(pr)
                if pr.author.lower() != self._author or event.id in imported:
                    continue
                checks = self._source.checks(repo, pr.head_sha)
                if checks is Checks.PASSED:
                    ready.append(event)
                elif checks is Checks.RUNNING:
                    waiting += 1
        added = self._store.append_new(ready)
        return GitHubResult(merged=len(added), waiting=waiting)
