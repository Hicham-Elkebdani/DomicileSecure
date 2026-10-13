from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class RulesConfig:
    night_start_hour: int = 23
    night_end_hour: int = 6
    door_open_max_seconds: int = 600
    recurring_visitor_threshold: int = 3

    def is_night(self, local_time: datetime) -> bool:
        hour = local_time.hour
        if self.night_start_hour > self.night_end_hour:  # window crosses midnight
            return hour >= self.night_start_hour or hour < self.night_end_hour
        return self.night_start_hour <= hour < self.night_end_hour
