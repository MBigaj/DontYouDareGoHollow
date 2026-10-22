import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import pytest

from hollow.adapters.anki_connect import AnkiConnect
from hollow.adapters.db.store import SqlEventStore
from hollow.application.anki_sync import LOOKBACK, AnkiSync, AnkiUnavailable, SyncResult
from hollow.domain.activities import ActivityKind
from hollow.domain.anki import AnkiReview, ReviewType, to_events
from hollow.domain.calendar import GameCalendar
from hollow.domain.events import Source, StudyLogged
from hollow.domain.vocabulary import LearnedWord
from tests.conftest import FakeClock

CAL = GameCalendar(ZoneInfo("Europe/Warsaw"), 4)


def ms(moment: datetime) -> int:
    return int(moment.timestamp() * 1000)


def review(at: datetime, *, card: int = 1, kind: int = 1, last: int = 3) -> AnkiReview:
    return AnkiReview(review_id=ms(at), card_id=card, review_type=kind, last_interval=last)


def first_sight(at: datetime, card: int = 1) -> AnkiReview:
    return review(at, card=card, kind=ReviewType.LEARN, last=0)


@dataclass
class FakeAnki:
    reviews: list[AnkiReview] = field(default_factory=list)
    asked_after: list[datetime] = field(default_factory=list)
    down: bool = False
    words: list[LearnedWord] = field(default_factory=list)

    def reviews_since(self, after: datetime) -> list[AnkiReview]:
        if self.down:
            raise AnkiUnavailable("closed")
        self.asked_after.append(after)
        return [r for r in self.reviews if r.reviewed_at > after]

    def learned_words(self, skip: frozenset[int]) -> list[LearnedWord]:
        return [w for w in self.words if w.note_id not in skip]


# --- mapping ------------------------------------------------------------------


def test_first_sight_is_a_new_card_and_later_answers_are_reviews() -> None:
    now = datetime(2026, 10, 20, 10, tzinfo=UTC)
    events = to_events(
        [
            first_sight(now),
            review(now + timedelta(minutes=1), kind=ReviewType.LEARN, last=-60),
            review(now + timedelta(minutes=2), kind=ReviewType.REVIEW),
            review(now + timedelta(minutes=3), kind=ReviewType.RELEARN),
        ]
    )
    assert [e.kind for e in events] == [
        ActivityKind.ANKI_NEW_CARDS,
        ActivityKind.ANKI_REVIEWS,
        ActivityKind.ANKI_REVIEWS,
        ActivityKind.ANKI_REVIEWS,
    ]
    assert all(e.source is Source.ANKI and e.quantity == 1 for e in events)
    assert events[0].occurred_at == now


def test_rescheduling_is_not_study_and_duplicates_collapse() -> None:
    now = datetime(2026, 10, 20, 10, tzinfo=UTC)
    events = to_events(
        [
            review(now),
            review(now),  # same review seen through two decks
            review(now + timedelta(seconds=5), kind=ReviewType.MANUAL),
            review(now + timedelta(seconds=9), kind=ReviewType.RESCHEDULED),
        ]
    )
    assert len(events) == 1


def test_imported_ids_are_deterministic() -> None:
    now = datetime(2026, 10, 20, 10, tzinfo=UTC)
    assert to_events([review(now)])[0].id == to_events([review(now)])[0].id


# --- sync use case ------------------------------------------------------------


def test_first_sync_starts_at_the_beginning_of_the_game(
    store: SqlEventStore, clock: FakeClock
) -> None:
    before_game = clock.now() - timedelta(days=30)
    anki = FakeAnki(
        [
            review(before_game),
            first_sight(clock.now()),
            review(clock.now() + timedelta(seconds=8), card=2),
        ]
    )

    result = AnkiSync(store, anki, clock, CAL).run()

    assert result == SyncResult(reviews=1, new_cards=1)
    # today 2026-10-20 began at 04:00 Warsaw = 02:00 UTC
    assert anki.asked_after[0] == datetime(2026, 10, 20, 2, tzinfo=UTC)


def test_first_sync_reaches_back_to_the_first_manual_log(
    store: SqlEventStore, clock: FakeClock
) -> None:
    three_days_ago = clock.now() - timedelta(days=3)
    store.append(StudyLogged(three_days_ago, ActivityKind.DEV_STUDY, 30))
    anki = FakeAnki([review(three_days_ago + timedelta(hours=1))])

    assert AnkiSync(store, anki, clock, CAL).run().reviews == 1


def test_syncing_twice_imports_nothing_new(store: SqlEventStore, clock: FakeClock) -> None:
    anki = FakeAnki([review(clock.now() - timedelta(seconds=n), card=n) for n in range(3)])
    sync = AnkiSync(store, anki, clock, CAL)

    assert sync.run().total == 3
    assert sync.run().total == 0
    assert len(store.all()) == 3
    # the second sync looks back, but never before the game began (04:00 Warsaw today)
    assert anki.asked_after[1] == datetime(2026, 10, 20, 2, tzinfo=UTC)


def test_late_phone_reviews_are_still_imported(store: SqlEventStore, clock: FakeClock) -> None:
    """A phone review reaches desktop Anki after newer desktop reviews were already imported."""
    store.append(StudyLogged(clock.now() - timedelta(days=5), ActivityKind.DEV_STUDY, 30))
    desktop = review(clock.now(), card=1)
    phone_yesterday = review(clock.now() - timedelta(days=1), card=2)
    anki = FakeAnki([desktop])
    sync = AnkiSync(store, anki, clock, CAL)
    assert sync.run().reviews == 1

    anki.reviews.append(phone_yesterday)  # arrives with the next AnkiWeb sync
    assert sync.run().reviews == 1
    assert anki.asked_after[1] == clock.now() - LOOKBACK


def test_overlapping_results_are_not_counted_twice(store: SqlEventStore, clock: FakeClock) -> None:
    class Overlapping(FakeAnki):
        def reviews_since(self, after: datetime) -> list[AnkiReview]:
            return self.reviews  # ignores the cursor, like a sloppy source

    anki = Overlapping([review(clock.now())])
    sync = AnkiSync(store, anki, clock, CAL)
    assert sync.run().total == 1
    assert sync.run().total == 0


def test_sync_errors_surface_to_the_caller(store: SqlEventStore, clock: FakeClock) -> None:
    with pytest.raises(AnkiUnavailable):
        AnkiSync(store, FakeAnki(down=True), clock, CAL).run()


# --- AnkiConnect adapter ------------------------------------------------------


def anki_server(decks: list[str], rows: dict[str, list[list[int]]], calls: list[dict[str, Any]]):  # type: ignore[no-untyped-def]
    def handle(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append(body)
        action = body["action"]
        if action == "version":
            return httpx.Response(200, json={"result": 6, "error": None})
        if action == "deckNames":
            return httpx.Response(200, json={"result": decks, "error": None})
        if action == "cardReviews":
            return httpx.Response(200, json={"result": rows[body["params"]["deck"]], "error": None})
        return httpx.Response(200, json={"result": None, "error": "unsupported action"})

    return httpx.MockTransport(handle)


def row(review_id: int, *, card: int = 7, last: int = 4, kind: int = 1) -> list[int]:
    return [review_id, card, -1, 3, 10, last, 2500, 6000, kind]


DECKS = ["Default", "Japanese", "Japanese::Core 2000", "Japanese::Core 2000::Kanji", "Rust"]
# Like the real cardReviews, each deck only returns reviews of cards sitting directly in it.
REVIEWS_BY_DECK = {
    "Default": [],
    "Japanese": [],
    "Japanese::Core 2000": [row(1_760_950_000_000), row(1_760_950_001_000, last=0, kind=0)],
    "Japanese::Core 2000::Kanji": [row(1_760_950_002_000, card=8)],
    "Rust": [row(1_760_950_003_000, card=9)],
}


def queried_decks(calls: list[dict[str, Any]]) -> list[str]:
    return [c["params"]["deck"] for c in calls if c["action"] == "cardReviews"]


def test_adapter_reads_every_deck_including_subdecks() -> None:
    calls: list[dict[str, Any]] = []
    anki = AnkiConnect(transport=anki_server(DECKS, REVIEWS_BY_DECK, calls))
    after = datetime(2025, 1, 1, tzinfo=UTC)

    reviews = anki.reviews_since(after)

    assert len(reviews) == 4
    assert reviews[1].is_first_sight
    assert queried_decks(calls) == DECKS
    assert all(c["version"] == 6 for c in calls)
    assert all(c["params"]["startID"] == ms(after) for c in calls if c["action"] == "cardReviews")


def test_a_named_deck_counts_with_its_subdecks() -> None:
    calls: list[dict[str, Any]] = []
    anki = AnkiConnect(
        decks=("Japanese::Core 2000",), transport=anki_server(DECKS, REVIEWS_BY_DECK, calls)
    )

    reviews = anki.reviews_since(datetime(2025, 1, 1, tzinfo=UTC))

    assert len(reviews) == 3
    assert queried_decks(calls) == ["Japanese::Core 2000", "Japanese::Core 2000::Kanji"]
    assert anki.missing_decks() == ()
    assert anki.version() == 6


def test_unknown_deck_names_are_never_queried() -> None:
    """AnkiConnect would create a deck for a name it does not know."""
    calls: list[dict[str, Any]] = []
    anki = AnkiConnect(
        decks=("Core 2000", "Rust"), transport=anki_server(DECKS, REVIEWS_BY_DECK, calls)
    )

    assert len(anki.reviews_since(datetime(2025, 1, 1, tzinfo=UTC))) == 1
    assert queried_decks(calls) == ["Rust"]
    assert anki.missing_decks() == ("Core 2000",)


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500),
        httpx.Response(200, content=b"not json"),
        httpx.Response(200, json=["no", "result"]),
        httpx.Response(200, json={"result": None, "error": "collection is not available"}),
    ],
)
def test_adapter_reports_unavailable_anki(response: httpx.Response) -> None:
    anki = AnkiConnect(transport=httpx.MockTransport(lambda request: response))
    with pytest.raises(AnkiUnavailable):
        anki.version()


def test_adapter_reports_a_closed_anki() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    with pytest.raises(AnkiUnavailable, match="Could not reach"):
        AnkiConnect(transport=httpx.MockTransport(refuse)).version()
