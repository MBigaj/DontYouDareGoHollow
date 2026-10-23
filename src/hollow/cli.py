"""Command-line entry points. `uv run hollow-sync-anki` can run from a scheduled task."""

import json
import sys
import time
from datetime import timedelta
from pathlib import Path

from hollow.adapters.anki_connect import connect
from hollow.adapters.db.store import SqlEventStore, make_engine
from hollow.adapters.github_api import GitHubApi
from hollow.adapters.vault import Vault
from hollow.application.agents import AgentDesk, AgentError
from hollow.application.anki_sync import AnkiSync, AnkiUnavailable
from hollow.application.github_sync import GitHubSync, GitHubUnavailable
from hollow.application.ports import SystemClock
from hollow.application.vault_sync import VaultSync
from hollow.config import Settings
from hollow.domain.activities import ActivityKind
from hollow.domain.anki import to_events


def sync_anki() -> int:
    settings = Settings()
    sync = AnkiSync(
        SqlEventStore(make_engine(settings.database_url)),
        connect(settings),
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
    anki = connect(settings)
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


def _desk() -> AgentDesk:
    settings = Settings()
    return AgentDesk(
        SqlEventStore(make_engine(settings.database_url)), SystemClock(), settings.calendar()
    )


def agent_inbox(argv: list[str] | None = None) -> int:
    """Writes the agents' inbox (agents/inbox/<day>.json) and lists its tasks."""
    args = sys.argv[1:] if argv is None else argv
    settings = Settings()
    if settings.vault_path:
        store = SqlEventStore(make_engine(settings.database_url))
        notes = VaultSync(store, Vault(Path(settings.vault_path)), SystemClock()).run()
        print(f"Vault scanned: {notes} note{'s' if notes != 1 else ''} updated.")
    inbox = _desk().inbox()
    path = Path(args[0]) if args else Path("agents") / "inbox" / f"{inbox['today']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(inbox, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Inbox written to {path}")
    if not inbox["tasks"]:
        print("Nothing is waiting for an agent.")
    for task in inbox["tasks"]:
        print(f"- {task['agent']}: {task['task']} · {task['do']}")
    return 0


def agent_submit(argv: list[str] | None = None) -> int:
    """Validates an agent result file and saves it, or explains why it was rejected."""
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("Usage: hollow-agent-submit <result.json>", file=sys.stderr)
        return 2
    try:
        saved = _desk().submit(Path(args[0]).read_text(encoding="utf-8"))
    except (OSError, AgentError) as error:
        print(f"Rejected: {error}", file=sys.stderr)
        return 1
    for event in saved:
        print(f"Saved {event.agent} result for {event.task}.")
    return 0
