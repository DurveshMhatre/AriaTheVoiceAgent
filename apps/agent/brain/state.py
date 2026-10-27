from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class CallState:
    intent: str = "OTHER"
    candidate_id: str | None = None
    confirmed_id: str | None = None
    id_attempts: int = 0
    unclear_turn_count: int = 0
    escalation_flag: bool = False
    escalation_reason: str | None = None
    pending_action: str | None = None
    pending_request: str | None = None
    verified: bool = False
    turn_count: int = 0
    interrupted: bool = False
    spoken_history: list[dict[str, str]] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    usage: dict[str, int] = field(
        default_factory=lambda: {"calls": 0, "input_tokens": 0, "output_tokens": 0, "latency_ms": 0}
    )

    def set_candidate(self, order_id: str) -> None:
        self.candidate_id = order_id
        self.confirmed_id = None

    def confirm_candidate(self, answer: bool | None) -> None:
        if answer is True and self.candidate_id:
            self.confirmed_id = self.candidate_id
        elif answer is False or answer is None:
            self.id_attempts += 1
            if self.id_attempts >= 2:
                self.escalation_flag = True
                self.escalation_reason = "REPEATED_FAILURE"

    def reset(self) -> None:
        self.candidate_id = None
        self.confirmed_id = None
        self.pending_action = None
        self.pending_request = None
        self.interrupted = False
        self.spoken_history.clear()
        self.tool_results.clear()
        self.usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "latency_ms": 0}

    def record_unclear(self) -> None:
        self.unclear_turn_count += 1
        if self.unclear_turn_count >= 3:
            self.escalation_flag = True
            self.escalation_reason = "REPEATED_FAILURE"

    def commit_spoken(self, turn_id: str, spoken_text: str) -> None:
        self.interrupted = True
        self.spoken_history = [
            item for item in self.spoken_history if item.get("turn_id") != turn_id
        ]
        self.spoken_history.append({"turn_id": turn_id, "text": spoken_text})

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
