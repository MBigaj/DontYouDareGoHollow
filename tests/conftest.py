from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from hollow.adapters.db.store import Base, SqlEventStore, make_engine
from hollow.adapters.web.app import create_app
from hollow.config import Settings


@dataclass
class FakeClock:
    current: datetime

    def now(self) -> datetime:
        return self.current

    def advance(self, days: int = 0, hours: int = 0) -> None:
        self.current += timedelta(days=days, hours=hours)


@pytest.fixture
def clock() -> FakeClock:
    # Noon in Warsaw on 2026-10-20
    return FakeClock(datetime(2026, 10, 20, 10, 0, tzinfo=UTC))


@pytest.fixture
def store() -> SqlEventStore:
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    return SqlEventStore(engine)


@pytest.fixture
def client(store: SqlEventStore, clock: FakeClock) -> Iterator[TestClient]:
    settings = Settings(database_url="sqlite://", _env_file=None)
    with TestClient(create_app(settings, store=store, clock=clock)) as test_client:
        yield test_client
