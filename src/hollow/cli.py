"""Command-line entry points. `uv run hollow-sync-anki` can run from a scheduled task."""

import sys

from hollow.adapters.anki_connect import AnkiConnect
from hollow.adapters.db.store import SqlEventStore, make_engine
from hollow.application.anki_sync import AnkiSync, AnkiUnavailable
from hollow.application.ports import SystemClock
from hollow.config import Settings


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
