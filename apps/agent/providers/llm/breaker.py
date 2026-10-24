from __future__ import annotations

from dataclasses import dataclass
from time import monotonic


@dataclass
class CircuitBreaker:
    threshold: int = 3
    cooldown_seconds: float = 30.0
    failures: int = 0
    opened_at: float | None = None

    @property
    def state(self) -> str:
        if self.opened_at is None:
            return "closed"
        if monotonic() - self.opened_at >= self.cooldown_seconds:
            return "half-open"
        return "open"

    def record_success(self) -> None:
        self.failures = 0
        self.opened_at = None

    def record_failure(self) -> None:
        self.failures += 1
        if self.failures >= self.threshold:
            self.opened_at = monotonic()

    def allow(self) -> bool:
        return self.state != "open"
