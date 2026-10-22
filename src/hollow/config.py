from zoneinfo import ZoneInfo

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from hollow.domain.calendar import GameCalendar


class Settings(BaseSettings):
    """Read from environment variables prefixed HOLLOW_ (or a .env file)."""

    model_config = SettingsConfigDict(env_prefix="HOLLOW_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./hollow.db"
    timezone: str = "Europe/Warsaw"
    day_start_hour: int = 4
    password: SecretStr | None = None
    """When set, every page asks for it (HTTP basic auth). Set it before deploying publicly."""

    anki_enabled: bool = False
    """Read reviews from Anki through the AnkiConnect add-on instead of logging them by hand."""
    anki_url: str = "http://127.0.0.1:8765"
    """127.0.0.1, not localhost: on Windows, localhost tries IPv6 first and stalls ~2s per call."""
    anki_decks: str = ""
    """Comma-separated deck names to count, e.g. "Core 2000". Empty counts every deck."""

    def anki_deck_names(self) -> tuple[str, ...]:
        return tuple(name.strip() for name in self.anki_decks.split(",") if name.strip())

    github_enabled: bool = False
    """Earn souls for your merged pull requests whose CI passed."""
    github_repos: str = "MBigaj/hollow-trials"
    """Comma-separated owner/name repos whose pull requests count."""
    github_author: str = "MBigaj"
    """Only pull requests opened by this GitHub user count."""
    github_token: SecretStr | None = None
    """A read-only fine-grained token. Needed for private repos; raises the rate limit."""

    def github_repo_names(self) -> tuple[str, ...]:
        return tuple(name.strip() for name in self.github_repos.split(",") if name.strip())

    @field_validator("timezone")
    @classmethod
    def _known_timezone(cls, value: str) -> str:
        ZoneInfo(value)
        return value

    def calendar(self) -> GameCalendar:
        return GameCalendar(ZoneInfo(self.timezone), self.day_start_hour)
