"""Turning Anki's review log into study events."""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import IntEnum
from uuid import UUID, uuid5

from hollow.domain.activities import ActivityKind
from hollow.domain.events import Source, StudyLogged

ANKI_NAMESPACE = UUID("6f1c0d6e-2b9b-4a8e-9a57-2f1b0c7d3a11")


class ReviewType(IntEnum):
    """Anki's revlog `type` column."""

    LEARN = 0
    REVIEW = 1
    RELEARN = 2
    FILTERED = 3
    MANUAL = 4
    RESCHEDULED = 5


STUDIED = {ReviewType.LEARN, ReviewType.REVIEW, ReviewType.RELEARN, ReviewType.FILTERED}


@dataclass(frozen=True)
class AnkiReview:
    """One row of Anki's review log. `review_id` is the review time in epoch milliseconds."""

    review_id: int
    card_id: int
    review_type: int
    last_interval: int

    @property
    def reviewed_at(self) -> datetime:
        return datetime.fromtimestamp(self.review_id / 1000, tz=UTC)

    @property
    def is_first_sight(self) -> bool:
        """The very first answer on a new card: a learning review with no previous interval."""
        return self.review_type == ReviewType.LEARN and self.last_interval == 0

    @property
    def counts(self) -> bool:
        return self.review_type in STUDIED


def to_event(review: AnkiReview) -> StudyLogged:
    """New cards count once, on first sight; every other answer is a review."""
    kind = ActivityKind.ANKI_NEW_CARDS if review.is_first_sight else ActivityKind.ANKI_REVIEWS
    return StudyLogged(
        occurred_at=review.reviewed_at,
        kind=kind,
        quantity=1,
        source=Source.ANKI,
        id=uuid5(ANKI_NAMESPACE, str(review.review_id)),
    )


def to_events(reviews: list[AnkiReview]) -> list[StudyLogged]:
    unique = {r.review_id: r for r in reviews if r.counts}
    return [to_event(unique[key]) for key in sorted(unique)]
