"""Game days. A day starts at a configurable hour so late-night study counts for the day before."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class GameCalendar:
    timezone: ZoneInfo
    day_start_hour: int = 4

    def __post_init__(self) -> None:
        if not 0 <= self.day_start_hour <= 23:
            raise ValueError("day_start_hour must be between 0 and 23")

    def day_of(self, moment: datetime) -> date:
        local = moment.astimezone(self.timezone)
        return (local - timedelta(hours=self.day_start_hour)).date()
