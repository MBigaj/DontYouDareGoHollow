from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

ROOT = Path(__file__).resolve().parents[1]


def test_migrations_build_the_schema_the_models_expect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOLLOW_DATABASE_URL", f"sqlite:///{tmp_path / 'hollow.db'}")
    config = Config(str(ROOT / "alembic.ini"))
    command.upgrade(config, "head")
    command.check(config)  # raises if the models and migrations disagree
    command.downgrade(config, "base")


def test_entry_point_builds_the_app(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOLLOW_DATABASE_URL", f"sqlite:///{tmp_path / 'x.db'}")
    from hollow.application.ports import SystemClock
    from hollow.main import app

    assert app.title == "DontYouDareGoHollow"
    assert SystemClock().now().tzinfo is not None
