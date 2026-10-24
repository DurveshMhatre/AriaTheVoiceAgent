from __future__ import annotations

from dataclasses import dataclass
from typing import Any, AsyncIterator, Protocol

from .events import event
from .guardrails import validate_output
from .ids import classify_yes_no, normalize_order_id
from .prompt import build_system_prompt
from .state import CallState


@dataclass(frozen=True)
class UserTurn:
    text: str
    confidence: float | None = None
    language: str = "en-IN"


@dataclass(frozen=True)
class BrainEvent:
    kind: str
    payload: dict[str, Any]


class LlmProvider(Protocol):
    async def generate(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], params: dict[str, Any]) -> AsyncIterator[dict[str, Any]]: ...


class Brain:
    def __init__(self, config: dict[str, Any], state: CallState, llm: LlmProvider, dispatcher: Any) -> None:
        self.config, self.state, self.llm, self.dispatcher = config, state, llm, dispatcher
        self.messages: list[dict[str, Any]] = []
        self.sequence = 0

    async def handle_turn(self, user_turn: UserTurn) -> AsyncIterator[BrainEvent]:
        self.state.turn_count += 1
        text = user_turn.text.strip()
        if not text or text.lower() in {"hmm", "[inaudible]", "noise"}:
            self.state.record_unclear()
            yield BrainEvent("SENTENCE", {"text": "I didn't catch that, could you repeat?", "index": 0})
            yield BrainEvent("DONE", {"escalation": self.state.escalation_flag})
            return
        if self.state.candidate_id and not self.state.confirmed_id and normalize_order_id(text) is None:
            answer = classify_yes_no(text)
            if answer is not None:
                self.state.confirm_candidate(answer)
                response = "Thank you. Let me check that for you." if answer else "Please tell me the order ID again."
                yield BrainEvent("SENTENCE", {"text": response, "index": 0})
                yield BrainEvent("DONE", {})
                return
        self.messages.append({"role": "user", "content": text})
        prompt = build_system_prompt(self.config, self.state.as_dict())
        generated = ""
        async for delta in self.llm.generate([{"role": "system", "content": prompt}, *self.messages], [], {"temperature": 0.1, "thinking_level": "minimal"}):
            if delta.get("tool_call"):
                yield BrainEvent("FILLER", {"text": "Let me check that for you."})
                yield BrainEvent("TOOL_CALL", delta["tool_call"])
                continue
            generated += str(delta.get("text", ""))
        checked = validate_output(generated, self.config, escalation=self.state.escalation_flag)
        yield BrainEvent("SENTENCE", {"text": checked.text, "index": 0})
        self.state.spoken_history.append({"turn_id": f"turn-{self.state.turn_count}", "text": checked.text})
        self.messages.append({"role": "assistant", "content": checked.text})
        yield BrainEvent("DONE", {"guardrail_triggered": checked.triggered})
