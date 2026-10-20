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

    @field_validator("timezone")
    @classmethod
    def _known_timezone(cls, value: str) -> str:
        ZoneInfo(value)
        return value

    def calendar(self) -> GameCalendar:
        return GameCalendar(ZoneInfo(self.timezone), self.day_start_hour)
