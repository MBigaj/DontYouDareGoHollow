"""Turning merged pull requests into study events."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid5

from hollow.domain.activities import ActivityKind
from hollow.domain.events import Source, StudyLogged

GITHUB_NAMESPACE = UUID("0b8f3c52-7d4e-4f0a-b1a6-5c2e9d81f3a7")


@dataclass(frozen=True)
class MergedPullRequest:
    repo: str
    """owner/name, e.g. MBigaj/hollow-trials"""
    number: int
    title: str
    author: str
    merged_at: datetime
    head_sha: str

    @property
    def key(self) -> str:
        return f"{self.repo.lower()}#{self.number}"


def to_event(pr: MergedPullRequest) -> StudyLogged:
    return StudyLogged(
        occurred_at=pr.merged_at,
        kind=ActivityKind.PULL_REQUEST,
        quantity=1,
        note=f"{pr.repo}#{pr.number} {pr.title}"[:280],
        source=Source.GITHUB,
        id=uuid5(GITHUB_NAMESPACE, pr.key),
    )
