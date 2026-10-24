from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


class Clock:
    def now(self) -> datetime:
        raise NotImplementedError


@dataclass(frozen=True)
class SystemClock(Clock):
    def now(self) -> datetime:
        return datetime.now(tz=IST)


@dataclass(frozen=True)
class FixedClock(Clock):
    value: datetime

    def now(self) -> datetime:
        if self.value.tzinfo is None:
            raise ValueError("FixedClock requires a timezone-aware datetime")
        return self.value.astimezone(IST)
