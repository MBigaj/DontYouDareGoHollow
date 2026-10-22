from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from hollow import cli
from hollow.application.anki_sync import AnkiUnavailable
from hollow.application.github_sync import Checks, GitHubUnavailable
from hollow.domain.anki import AnkiReview
from hollow.domain.github import MergedPullRequest
from hollow.domain.vocabulary import LearnedWord

ROOT = Path(__file__).resolve().parents[1]


class StubAnki:
    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    def learned_words(self, skip: frozenset[int]) -> list[LearnedWord]:
        return [LearnedWord(1, "食べる", "たべる", "eat", "Verb")]

    def version(self) -> int:
        return 6

    def decks(self) -> tuple[str, ...]:
        return ("Core 2000",)

    def missing_decks(self) -> tuple[str, ...]:
        return ()

    def reviews_since(self, after: datetime) -> list[AnkiReview]:
        just_now = datetime.now(UTC) - timedelta(minutes=1)
        return [AnkiReview(int(just_now.timestamp() * 1000), 1, 1, 3)]


class TypoAnki(StubAnki):
    def missing_decks(self) -> tuple[str, ...]:
        return ("Core 200",)


class SlowAnki(StubAnki):
    def version(self) -> int:
        import time

        time.sleep(0.6)
        return 6


class ClosedAnki(StubAnki):
    def version(self) -> int:
        raise AnkiUnavailable("Could not reach AnkiConnect")

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
    monkeypatch.setattr(cli, "connect", StubAnki)
    assert cli.sync_anki() == 0
    assert "Imported 1 reviews and 0 new cards" in capsys.readouterr().out


@pytest.mark.usefixtures("database")
def test_sync_command_fails_cleanly_when_anki_is_closed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "connect", ClosedAnki)
    assert cli.sync_anki() == 1
    assert "Could not reach AnkiConnect" in capsys.readouterr().err


def test_check_reports_what_anki_sees(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "connect", StubAnki)
    assert cli.check_anki() == 0
    out = capsys.readouterr().out
    assert "version 6" in out
    assert "Decks read:        Core 2000" in out
    assert "1 reviews, 0 new cards in Anki" in out
    assert "Slow" not in out


def test_check_flags_a_slow_connection(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "connect", SlowAnki)
    assert cli.check_anki() == 0
    assert "use http://127.0.0.1:8765" in capsys.readouterr().out


def test_check_explains_a_closed_anki(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "connect", ClosedAnki)
    assert cli.check_anki() == 1
    assert "Could not reach AnkiConnect" in capsys.readouterr().err


def test_check_flags_deck_names_anki_does_not_know(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "connect", TypoAnki)
    assert cli.check_anki() == 0
    assert "Not found in Anki: Core 200" in capsys.readouterr().out


class StubGitHub:
    def __init__(self, token: str | None = None) -> None:
        pass

    def merged_pull_requests(self, repo: str, since: datetime) -> list[MergedPullRequest]:
        just_now = datetime.now(UTC) - timedelta(seconds=5)
        return [
            MergedPullRequest(repo, 1, "Trial", "MBigaj", just_now, "sha1"),
            MergedPullRequest(repo, 2, "Trial", "MBigaj", just_now, "sha2"),
        ]

    def checks(self, repo: str, sha: str) -> Checks:
        return Checks.PASSED if sha == "sha1" else Checks.RUNNING


class DownGitHub(StubGitHub):
    def merged_pull_requests(self, repo: str, since: datetime) -> list[MergedPullRequest]:
        raise GitHubUnavailable("Could not reach GitHub")


@pytest.mark.usefixtures("database")
def test_github_sync_command_imports_prs(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "GitHubApi", StubGitHub)
    assert cli.sync_github() == 0
    out = capsys.readouterr().out
    assert "Imported 1 merged pull requests" in out
    assert "1 merged pull requests are still waiting for CI" in out


@pytest.mark.usefixtures("database")
def test_github_sync_command_fails_cleanly(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "GitHubApi", DownGitHub)
    assert cli.sync_github() == 1
    assert "Could not reach GitHub" in capsys.readouterr().err
