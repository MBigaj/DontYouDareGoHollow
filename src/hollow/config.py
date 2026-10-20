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
    anki_url: str = "http://localhost:8765"
    anki_decks: str = ""
    """Comma-separated deck names to count, e.g. "Core 2000". Empty counts every deck."""

    def anki_deck_names(self) -> tuple[str, ...]:
        return tuple(name.strip() for name in self.anki_decks.split(",") if name.strip())

    @field_validator("timezone")
    @classmethod
    def _known_timezone(cls, value: str) -> str:
        ZoneInfo(value)
        return value

    def calendar(self) -> GameCalendar:
        return GameCalendar(ZoneInfo(self.timezone), self.day_start_hour)
