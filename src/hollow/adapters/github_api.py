"""GitHub REST client for merged pull requests and their CI results."""

from datetime import datetime
from typing import Any

import httpx

from hollow.application.github_sync import Checks, GitHubUnavailable
from hollow.domain.github import MergedPullRequest

API = "https://api.github.com"
PAGE_SIZE = 50
MAX_PAGES = 5
OK_CONCLUSIONS = {"success", "neutral", "skipped"}


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class GitHubApi:
    def __init__(
        self,
        token: str | None = None,
        timeout: float = 5.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "DontYouDareGoHollow",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.Client(
            base_url=API, headers=headers, timeout=timeout, transport=transport
        )

    def merged_pull_requests(self, repo: str, since: datetime) -> list[MergedPullRequest]:
        """Closed pull requests, newest update first, until updates fall before `since`."""
        found: list[MergedPullRequest] = []
        for page in range(1, MAX_PAGES + 1):
            pulls: list[dict[str, Any]] = self._get(
                f"/repos/{repo}/pulls",
                state="closed",
                sort="updated",
                direction="desc",
                per_page=PAGE_SIZE,
                page=page,
            )
            for pull in pulls:
                merged_at = pull.get("merged_at")
                if merged_at and parse_time(merged_at) > since:
                    found.append(
                        MergedPullRequest(
                            repo=repo,
                            number=int(pull["number"]),
                            title=str(pull["title"]),
                            author=str(pull["user"]["login"]),
                            merged_at=parse_time(merged_at),
                            head_sha=str(pull["head"]["sha"]),
                        )
                    )
            if len(pulls) < PAGE_SIZE or parse_time(pulls[-1]["updated_at"]) < since:
                break
        return found

    def checks(self, repo: str, sha: str) -> Checks:
        """Combines GitHub Actions check runs with legacy commit statuses."""
        runs: list[dict[str, Any]] = self._get(
            f"/repos/{repo}/commits/{sha}/check-runs", per_page=100
        )["check_runs"]
        status: dict[str, Any] = self._get(f"/repos/{repo}/commits/{sha}/status")
        statuses: list[dict[str, Any]] = status.get("statuses", [])

        if not runs and not statuses:
            return Checks.NONE
        if any(run["status"] != "completed" for run in runs) or any(
            s["state"] == "pending" for s in statuses
        ):
            return Checks.RUNNING
        if any(run["conclusion"] not in OK_CONCLUSIONS for run in runs) or any(
            s["state"] != "success" for s in statuses
        ):
            return Checks.FAILED
        return Checks.PASSED

    def _get(self, path: str, **params: Any) -> Any:
        try:
            response = self._client.get(path, params=params)
        except httpx.HTTPError as error:
            raise GitHubUnavailable("Could not reach GitHub") from error
        if response.status_code in (401, 403, 429):
            raise GitHubUnavailable(
                f"GitHub refused the request ({response.status_code}): "
                "check HOLLOW_GITHUB_TOKEN or wait for the rate limit to reset"
            )
        if response.status_code == 404:
            raise GitHubUnavailable(
                f"GitHub could not find {path.split('/')[2]}/{path.split('/')[3]}: "
                "check HOLLOW_GITHUB_REPOS, or the token's access to it"
            )
        try:
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise GitHubUnavailable("GitHub returned an unexpected response") from error
