from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Protocol, cast

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
    def generate(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], params: dict[str, Any]
    ) -> AsyncIterator[dict[str, Any]]: ...


async def _collect(
    provider: LlmProvider,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    params: dict[str, Any],
) -> list[dict[str, Any]]:
    return [item async for item in provider.generate(messages, tools, params)]


class Brain:
    def __init__(
        self,
        config: dict[str, Any],
        state: CallState,
        llm: LlmProvider,
        dispatcher: Any,
        turn_deadline_seconds: float = 12.0,
    ) -> None:
        self.config, self.state, self.llm, self.dispatcher = config, state, llm, dispatcher
        self.messages: list[dict[str, Any]] = []
        self.turn_deadline_seconds = turn_deadline_seconds
        self.tool_round_limit = 3
        self._turn_id = 0

    def _tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "get_order_details",
                "description": "Get facts for a confirmed Aura order.",
                "input_schema": {
                    "type": "object",
                    "properties": {"order_id": {"type": "string"}},
                    "required": ["order_id"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "check_return_eligibility",
                "description": (
                    "Compute return or damage eligibility from order facts or a customer claim."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "order_id": {"type": "string"},
                        "days_since_delivery": {"type": "number"},
                        "opened": {"type": "boolean"},
                        "issue_type": {"type": "string"},
                    },
                    "required": [],
                    "additionalProperties": False,
                },
            },
            {
                "name": "cancel_order",
                "description": (
                    "Cancel a confirmed Processing order after explicit customer confirmation."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "order_id": {"type": "string"},
                        "idempotency_key": {"type": "string"},
                    },
                    "required": ["order_id", "idempotency_key"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "escalate_to_human",
                "description": "Record a support follow-up; never claim a live transfer.",
                "input_schema": {
                    "type": "object",
                    "properties": {"reason": {"type": "string"}, "note": {"type": "string"}},
                    "required": ["reason"],
                    "additionalProperties": False,
                },
            },
        ]

    def _dispatch(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        method = (
            getattr(self.dispatcher, name, None)
            if isinstance(name, str) and name in {tool["name"] for tool in self._tools()}
            else None
        )
        if method is None or not isinstance(arguments, dict):
            return {
                "ok": False,
                "data": None,
                "error_code": "INVALID_FORMAT",
                "speakable_hint": "I cannot complete that request.",
            }
        try:
            return cast(dict[str, Any], method(**arguments))
        except (TypeError, ValueError, KeyError):
            return {
                "ok": False,
                "data": None,
                "error_code": "INVALID_FORMAT",
                "speakable_hint": "I need a little more information.",
            }

    async def _confirmation_turn(self, text: str) -> tuple[str, dict[str, Any] | None]:
        if self.state.pending_action:
            answer = classify_yes_no(text)
            if answer is True and self.state.pending_action.startswith("cancel:"):
                order_id = self.state.pending_action.split(":", 1)[1]
                tool_result = self._dispatch(
                    "cancel_order",
                    {"order_id": order_id, "idempotency_key": f"turn-{self._turn_id}-{order_id}"},
                )
                self.state.pending_action = None
                return "", tool_result
            if answer is False:
                self.state.pending_action = None
                return "I will not cancel the order.", None
            return "Please answer yes or no so I know whether to continue.", None
        if self.state.candidate_id and not self.state.confirmed_id:
            answer = classify_yes_no(text)
            if answer is not None:
                self.state.confirm_candidate(answer)
                if answer is True:
                    original = self.state.pending_request or "Please help with my confirmed order."
                    self.state.pending_request = None
                    return original, None
                return "Please tell me the order ID again.", None
        return text, None

    async def handle_turn(self, user_turn: UserTurn) -> AsyncIterator[BrainEvent]:
        started = time.perf_counter()
        self._turn_id += 1
        self.state.turn_count += 1
        text = user_turn.text.strip()
        if (
            not text
            or text.lower() in {"hmm", "[inaudible]", "noise"}
            or (user_turn.confidence is not None and user_turn.confidence < 0.35)
        ):
            self.state.record_unclear()
            sentence = "I didn't catch that, could you repeat?"
            if self.state.escalation_flag:
                sentence += " The support team can follow up if needed."
            self._record(sentence)
            yield BrainEvent("SENTENCE", {"text": sentence, "index": 0})
            yield BrainEvent(
                "DONE",
                {
                    "escalation": self.state.escalation_flag,
                    "latency_ms": int((time.perf_counter() - started) * 1000),
                },
            )
            return

        candidate = normalize_order_id(text)
        if candidate and not self.state.confirmed_id:
            self.state.set_candidate(candidate)
            self.state.pending_request = text
            sentence = f"I heard {candidate.replace('-', ' ')}. Please confirm that order ID."
            self._record(sentence)
            yield BrainEvent("SENTENCE", {"text": sentence, "index": 0})
            yield BrainEvent("DONE", {"confirmation_required": True})
            return

        text, direct_result = await self._confirmation_turn(text)
        if direct_result is not None:
            yield BrainEvent("FILLER", {"text": "Let me check that for you."})
            yield BrainEvent(
                "TOOL_CALL",
                {
                    "name": "cancel_order",
                    "arguments": {"order_id": self.state.confirmed_id},
                    "call_id": f"turn-{self._turn_id}",
                },
            )
            yield BrainEvent("TOOL_RESULT", direct_result)
            sentence = (
                "The order cancellation request was completed."
                if direct_result.get("ok")
                else (direct_result.get("speakable_hint") or "I could not cancel that order.")
            )
            checked = validate_output(sentence, self.config, escalation=self.state.escalation_flag)
            self._record(checked.text)
            yield BrainEvent("SENTENCE", {"text": checked.text, "index": 0})
            yield BrainEvent("DONE", {"guardrail_triggered": checked.triggered})
            return
        if text != user_turn.text.strip() and text.startswith("Please"):
            self._record(text)
            yield BrainEvent("SENTENCE", {"text": text, "index": 0})
            yield BrainEvent("DONE", {})
            return

        self.messages.append({"role": "user", "content": text})
        deadline = time.perf_counter() + self.turn_deadline_seconds
        final_text = ""
        guardrail_triggered = False
        for round_index in range(self.tool_round_limit + 1):
            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                final_text = "I need a little more time to check that. Please try again."
                break
            params = {"temperature": 0.1, "thinking_level": "minimal", "max_output_tokens": 160}
            try:
                outputs = await asyncio.wait_for(
                    _collect(
                        self.llm,
                        [
                            {
                                "role": "system",
                                "content": build_system_prompt(self.config, self.state.as_dict()),
                            },
                            *self.messages,
                        ],
                        self._tools(),
                        params,
                    ),
                    timeout=remaining,
                )
            except TimeoutError:
                final_text = "I need a little more time to check that. Please try again."
                break
            tool_calls = [item["tool_call"] for item in outputs if item.get("tool_call")]
            text_parts = [str(item.get("text", "")) for item in outputs if item.get("text")]
            if not tool_calls:
                final_text = "".join(text_parts) or "I don't have that information yet."
                break
            if round_index >= self.tool_round_limit:
                final_text = (
                    "I could not complete that check within the limit. "
                    "The support team can follow up if needed."
                )
                break
            stop_for_customer_confirmation = False
            self.messages.append(
                {
                    "role": "assistant",
                    "tool_calls": tool_calls,
                    "content": "".join(text_parts),
                }
            )
            for call in tool_calls:
                yield BrainEvent("FILLER", {"text": "Let me check that for you."})
                yield BrainEvent("TOOL_CALL", call)
                arguments = call.get("arguments", {})
                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments)
                    except json.JSONDecodeError:
                        arguments = {}
                result = self._dispatch(call.get("name", ""), arguments)
                self.state.tool_results.append(
                    {"name": call.get("name"), "arguments": arguments, "result": result}
                )
                yield BrainEvent("TOOL_RESULT", {"name": call.get("name"), "result": result})
                self.messages.append(
                    {
                        "role": "tool",
                        "name": call.get("name"),
                        "tool_call_id": call.get("call_id"),
                        "content": json.dumps(result),
                    }
                )
                if (
                    call.get("name") == "cancel_order"
                    and not result.get("ok")
                    and result.get("error_code") == "MISSING_ARGUMENT"
                ):
                    final_text = (
                        result.get("speakable_hint") or "Please confirm that you want to cancel it."
                    )
                    stop_for_customer_confirmation = True
            if stop_for_customer_confirmation:
                break
        checked = validate_output(final_text, self.config, escalation=self.state.escalation_flag)
        guardrail_triggered = checked.triggered
        sentences = [
            part.strip()
            for part in checked.text.replace("!", ".").replace("?", ".").split(".")
            if part.strip()
        ]
        for index, sentence in enumerate(sentences[:2]):
            self._record(sentence + ".")
            yield BrainEvent("SENTENCE", {"text": sentence + ".", "index": index})
        self.messages.append({"role": "assistant", "content": checked.text})
        self.state.usage["calls"] += 1
        self.state.usage["latency_ms"] += int((time.perf_counter() - started) * 1000)
        yield BrainEvent(
            "DONE",
            {
                "guardrail_triggered": guardrail_triggered,
                "latency_ms": int((time.perf_counter() - started) * 1000),
            },
        )

    def _record(self, text: str) -> None:
        self.state.spoken_history.append({"turn_id": f"turn-{self._turn_id}", "text": text})

    def commit_spoken(self, spoken_text: str) -> None:
        turn_id = f"turn-{self._turn_id}"
        self.state.commit_spoken(turn_id, spoken_text)
        if not spoken_text:
            return
        if self.messages and self.messages[-1].get("role") == "assistant":
            self.messages[-1]["content"] = spoken_text
        else:
            self.messages.append({"role": "assistant", "content": spoken_text})
