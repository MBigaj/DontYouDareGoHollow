from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from hollow.adapters.db.store import EventRow, SqlEventStore, UTCDateTime, from_row
from hollow.domain.activities import ActivityKind
from hollow.domain.events import MessageLeft, Source, StudyLogged


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


def test_append_new_skips_events_already_stored(store: SqlEventStore) -> None:
    first = StudyLogged(datetime.now(UTC), ActivityKind.ANKI_REVIEWS, 1, source=Source.ANKI)
    second = StudyLogged(datetime.now(UTC), ActivityKind.ANKI_REVIEWS, 1, source=Source.ANKI)

    assert store.append_new([first]) == [first]
    assert store.append_new([first, second]) == [second]
    assert store.append_new([]) == []
    assert {e.id for e in store.all()} == {first.id, second.id}
    assert all(isinstance(e, StudyLogged) and e.source is Source.ANKI for e in store.all())


def test_stat_purchases_round_trip(store: SqlEventStore) -> None:
    from datetime import UTC, datetime

    from hollow.domain.events import StatLevelled
    from hollow.domain.progression import Stat

    event = StatLevelled(datetime(2026, 10, 22, 18, tzinfo=UTC), Stat.ENDURANCE, 240)
    store.append(event)
    assert store.all() == [event]
