from datetime import datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from hollow import cli
from hollow.application.anki_sync import AnkiUnavailable
from hollow.domain.anki import AnkiReview

ROOT = Path(__file__).resolve().parents[1]


class StubAnki:
    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    def reviews_since(self, after: datetime) -> list[AnkiReview]:
        return [AnkiReview(int(after.timestamp() * 1000) + 1000, 1, 1, 3)]


class ClosedAnki(StubAnki):
    def reviews_since(self, after: datetime) -> list[AnkiReview]:
        raise AnkiUnavailable("Could not reach AnkiConnect")


@pytest.fixture
def database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOLLOW_DATABASE_URL", f"sqlite:///{tmp_path / 'hollow.db'}")
    command.upgrade(Config(str(ROOT / "alembic.ini")), "head")


@pytest.mark.usefixtures("database")
def test_sync_command_imports_reviews(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "AnkiConnect", StubAnki)
    assert cli.sync_anki() == 0
    assert "Imported 1 reviews and 0 new cards" in capsys.readouterr().out


@pytest.mark.usefixtures("database")
def test_sync_command_fails_cleanly_when_anki_is_closed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "AnkiConnect", ClosedAnki)
    assert cli.sync_anki() == 1
    assert "Could not reach AnkiConnect" in capsys.readouterr().err
