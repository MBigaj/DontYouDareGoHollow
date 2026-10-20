from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from hollow.adapters.db.store import EventRow, SqlEventStore, UTCDateTime, from_row
from hollow.domain.activities import ActivityKind
from hollow.domain.events import MessageLeft, StudyLogged


def test_round_trips_events_in_time_order(store: SqlEventStore) -> None:
    later = StudyLogged(datetime(2026, 10, 2, 9, tzinfo=UTC), ActivityKind.DEV_STUDY, 30, "MVCC")
    earlier = MessageLeft(datetime(2026, 10, 1, 21, tzinfo=timezone(timedelta(hours=2))), "hi")
    store.append(later)
    store.append(earlier)

    events = store.all()

    assert events == [earlier, later]
    assert all(e.occurred_at.tzinfo is not None for e in events)


def test_unknown_event_type_is_rejected() -> None:
    row = EventRow(id="x", type="mystery", occurred_at=datetime.now(UTC), payload={})
    with pytest.raises(ValueError, match="unknown event type"):
        from_row(row)


def test_naive_datetimes_cannot_be_stored(store: SqlEventStore) -> None:
    column = UTCDateTime()
    with pytest.raises(ValueError):
        column.process_bind_param(datetime(2026, 1, 1), dialect=None)
    assert column.process_bind_param(None, dialect=None) is None
    assert column.process_result_value(None, dialect=None) is None
    aware = datetime(2026, 1, 1, tzinfo=timezone(timedelta(hours=2)))
    assert column.process_result_value(aware, dialect=None) == aware


def test_rows_are_append_only_records(store: SqlEventStore) -> None:
    store.append(StudyLogged(datetime.now(UTC), ActivityKind.ANKI_REVIEWS, 10))
    with Session(store._engine) as session:
        assert session.query(EventRow).count() == 1
