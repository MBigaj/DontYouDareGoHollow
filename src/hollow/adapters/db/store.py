"""SQLAlchemy event store: one append-only table, one row per event."""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, DateTime, Engine, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import TypeDecorator

from hollow.domain.activities import ActivityKind
from hollow.domain.events import (
    Event,
    FightAction,
    FightStarted,
    FightTurn,
    LessonCompleted,
    MessageLeft,
    Source,
    StatLevelled,
    StudyLogged,
    WordLearned,
)
from hollow.domain.progression import Stat


class Base(DeclarativeBase):
    pass


class UTCDateTime(TypeDecorator[datetime]):
    """Stores aware datetimes as UTC and always returns them aware (SQLite drops the zone)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("naive datetimes are not allowed")
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class EventRow(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    type: Mapped[str] = mapped_column(String(32))
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)


def to_row(event: Event) -> EventRow:
    if isinstance(event, StudyLogged):
        payload: dict[str, Any] = {
            "kind": event.kind.value,
            "quantity": event.quantity,
            "note": event.note,
            "source": event.source.value,
        }
        return EventRow(
            id=str(event.id), type="study_logged", occurred_at=event.occurred_at, payload=payload
        )
    if isinstance(event, FightStarted):
        return EventRow(
            id=str(event.id),
            type="fight_started",
            occurred_at=event.occurred_at,
            payload={
                "boss_id": event.boss_id,
                "seed": event.seed,
                "max_hp": event.max_hp,
                "mistake_cost": event.mistake_cost,
            },
        )
    if isinstance(event, FightTurn):
        return EventRow(
            id=str(event.id),
            type="fight_turn",
            occurred_at=event.occurred_at,
            payload={
                "attempt_id": str(event.attempt_id),
                "action": event.action.value,
                "correct": event.correct,
            },
        )
    if isinstance(event, LessonCompleted):
        return EventRow(
            id=str(event.id),
            type="lesson_completed",
            occurred_at=event.occurred_at,
            payload={"lesson_id": event.lesson_id, "correct": event.correct, "total": event.total},
        )
    if isinstance(event, WordLearned):
        return EventRow(
            id=str(event.id),
            type="word_learned",
            occurred_at=event.occurred_at,
            payload={
                "note_id": event.note_id,
                "written": event.written,
                "kana": event.kana,
                "meaning": event.meaning,
                "part_of_speech": event.part_of_speech,
            },
        )
    if isinstance(event, StatLevelled):
        return EventRow(
            id=str(event.id),
            type="stat_levelled",
            occurred_at=event.occurred_at,
            payload={"stat": event.stat.value, "cost": event.cost},
        )
    return EventRow(
        id=str(event.id),
        type="message_left",
        occurred_at=event.occurred_at,
        payload={"text": event.text},
    )


def from_row(row: EventRow) -> Event:
    p = row.payload
    if row.type == "study_logged":
        return StudyLogged(
            occurred_at=row.occurred_at,
            kind=ActivityKind(p["kind"]),
            quantity=int(p["quantity"]),
            note=str(p.get("note", "")),
            source=Source(p.get("source", Source.MANUAL.value)),
            id=UUID(row.id),
        )
    if row.type == "fight_started":
        return FightStarted(
            occurred_at=row.occurred_at,
            boss_id=str(p["boss_id"]),
            seed=int(p["seed"]),
            max_hp=int(p["max_hp"]),
            mistake_cost=int(p["mistake_cost"]),
            id=UUID(row.id),
        )
    if row.type == "fight_turn":
        return FightTurn(
            occurred_at=row.occurred_at,
            attempt_id=UUID(str(p["attempt_id"])),
            action=FightAction(p["action"]),
            correct=bool(p["correct"]),
            id=UUID(row.id),
        )
    if row.type == "lesson_completed":
        return LessonCompleted(
            occurred_at=row.occurred_at,
            lesson_id=str(p["lesson_id"]),
            correct=int(p["correct"]),
            total=int(p["total"]),
            id=UUID(row.id),
        )
    if row.type == "word_learned":
        return WordLearned(
            occurred_at=row.occurred_at,
            note_id=int(p["note_id"]),
            written=str(p["written"]),
            kana=str(p["kana"]),
            meaning=str(p["meaning"]),
            part_of_speech=str(p["part_of_speech"]),
            id=UUID(row.id),
        )
    if row.type == "stat_levelled":
        return StatLevelled(
            occurred_at=row.occurred_at, stat=Stat(p["stat"]), cost=int(p["cost"]), id=UUID(row.id)
        )
    if row.type == "message_left":
        return MessageLeft(occurred_at=row.occurred_at, text=str(p["text"]), id=UUID(row.id))
    raise ValueError(f"unknown event type: {row.type}")


class SqlEventStore:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def append(self, event: Event) -> None:
        with Session(self._engine) as session, session.begin():
            session.add(to_row(event))

    def append_new(self, events: Sequence[Event]) -> list[Event]:
        """Appends the events whose ids are not stored yet and returns them."""
        if not events:
            return []
        ids = [str(event.id) for event in events]
        with Session(self._engine) as session, session.begin():
            existing = set(session.scalars(select(EventRow.id).where(EventRow.id.in_(ids))))
            fresh = {str(e.id): e for e in events if str(e.id) not in existing}
            session.add_all(to_row(event) for event in fresh.values())
            return list(fresh.values())

    def all(self) -> Sequence[Event]:
        with Session(self._engine) as session:
            rows = session.scalars(select(EventRow).order_by(EventRow.occurred_at, EventRow.id))
            return [from_row(row) for row in rows]


def make_engine(url: str) -> Engine:
    if url in ("sqlite://", "sqlite:///:memory:"):
        return create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False})
    return create_engine(url, pool_pre_ping=True)
