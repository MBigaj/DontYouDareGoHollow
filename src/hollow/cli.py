"""Command-line entry points. `uv run hollow-sync-anki` can run from a scheduled task."""

import sys
import time
from datetime import timedelta

from hollow.adapters.anki_connect import AnkiConnect
from hollow.adapters.db.store import SqlEventStore, make_engine
from hollow.adapters.github_api import GitHubApi
from hollow.application.anki_sync import AnkiSync, AnkiUnavailable
from hollow.application.github_sync import GitHubSync, GitHubUnavailable
from hollow.application.ports import SystemClock
from hollow.config import Settings
from hollow.domain.activities import ActivityKind
from hollow.domain.anki import to_events


def sync_anki() -> int:
    settings = Settings()
    sync = AnkiSync(
        SqlEventStore(make_engine(settings.database_url)),
        AnkiConnect(settings.anki_url, settings.anki_deck_names()),
        SystemClock(),
        settings.calendar(),
    )
    try:
        result = sync.run()
    except AnkiUnavailable as error:
        print(error, file=sys.stderr)
        return 1
    print(f"Imported {result.reviews} reviews and {result.new_cards} new cards from Anki.")
    return 0


def check_anki() -> int:
    """Prints what the app can see in Anki, to debug a sync that looks wrong."""
    settings = Settings()
    anki = AnkiConnect(settings.anki_url, settings.anki_deck_names())
    calendar = settings.calendar()
    print(f"Anki sync enabled: {settings.anki_enabled}")
    print(f"AnkiConnect URL:   {settings.anki_url}")
    try:
        started = time.perf_counter()
        version = anki.version()
        elapsed_ms = (time.perf_counter() - started) * 1000
        print(f"AnkiConnect:       version {version}, answered in {elapsed_ms:.0f} ms")
        decks = anki.decks()
        print(f"Decks read:        {', '.join(decks) or '(none)'}")
        missing = anki.missing_decks()
        if missing:
            print(f"Not found in Anki: {', '.join(missing)} (check HOLLOW_ANKI_DECKS)")
        now = SystemClock().now()
        events = to_events(anki.reviews_since(now - timedelta(days=1)))
    except AnkiUnavailable as error:
        print(f"Problem:           {error}", file=sys.stderr)
        return 1
    today = calendar.day_of(now)
    todays = [e for e in events if calendar.day_of(e.occurred_at) == today]
    new = sum(1 for e in todays if e.kind is ActivityKind.ANKI_NEW_CARDS)
    print(f"Today ({today}):  {len(todays) - new} reviews, {new} new cards in Anki")
    if elapsed_ms > 500:
        print("Slow: use http://127.0.0.1:8765 rather than localhost in HOLLOW_ANKI_URL.")
    return 0


def sync_github() -> int:
    settings = Settings()
    token = settings.github_token.get_secret_value() if settings.github_token else None
    sync = GitHubSync(
        SqlEventStore(make_engine(settings.database_url)),
        GitHubApi(token),
        SystemClock(),
        settings.calendar(),
        settings.github_repo_names(),
        settings.github_author,
    )
    try:
        result = sync.run(force=True)
    except GitHubUnavailable as error:
        print(error, file=sys.stderr)
        return 1
    assert result is not None  # a forced run is never throttled
    print(f"Imported {result.merged} merged pull requests from GitHub.")
    if result.waiting:
        print(f"{result.waiting} merged pull requests are still waiting for CI.")
    return 0
