"""What counts as study, what it is worth, and how much of it lights the bonfire."""

from dataclasses import dataclass
from enum import StrEnum


class ActivityKind(StrEnum):
    ANKI_REVIEWS = "anki_reviews"
    ANKI_NEW_CARDS = "anki_new_cards"
    GRAMMAR_DRILL = "grammar_drill"
    JAPANESE_STUDY = "japanese_study"
    DEV_STUDY = "dev_study"
    PULL_REQUEST = "pull_request"


class Track(StrEnum):
    RONIN = "ronin"
    ARCHITECT = "architect"


@dataclass(frozen=True)
class ActivitySpec:
    kind: ActivityKind
    label: str
    unit: str
    track: Track
    souls_per_unit: int
    kindling: int
    """How much of this activity in one day is enough to light the bonfire on its own."""


ACTIVITIES: dict[ActivityKind, ActivitySpec] = {
    spec.kind: spec
    for spec in (
        ActivitySpec(ActivityKind.ANKI_REVIEWS, "Anki reviews", "reviews", Track.RONIN, 2, 10),
        ActivitySpec(ActivityKind.ANKI_NEW_CARDS, "New Anki cards", "cards", Track.RONIN, 5, 5),
        ActivitySpec(ActivityKind.GRAMMAR_DRILL, "Grammar drills", "drills", Track.RONIN, 20, 1),
        ActivitySpec(ActivityKind.JAPANESE_STUDY, "Japanese study", "minutes", Track.RONIN, 2, 5),
        ActivitySpec(ActivityKind.DEV_STUDY, "Dev study", "minutes", Track.ARCHITECT, 2, 5),
        ActivitySpec(
            ActivityKind.PULL_REQUEST, "Merged pull requests", "PRs", Track.ARCHITECT, 100, 1
        ),
    )
}

LIGHT_THE_BONFIRE = (ActivityKind.ANKI_REVIEWS, ACTIVITIES[ActivityKind.ANKI_REVIEWS].kindling)
"""The one-tap action: the smallest amount of study that keeps the fire lit."""


def souls_for(kind: ActivityKind, quantity: int) -> int:
    return ACTIVITIES[kind].souls_per_unit * quantity


def lights_bonfire(totals: dict[ActivityKind, int]) -> bool:
    """A day is lit once any single activity reaches its kindling amount."""
    return any(totals.get(kind, 0) >= spec.kindling for kind, spec in ACTIVITIES.items())
