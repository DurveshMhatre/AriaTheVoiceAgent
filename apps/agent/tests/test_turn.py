import asyncio

from brain.clock import FixedClock
from brain.config import TenantConfigLoader
from brain.repo import InMemoryOrderRepository
from brain.state import CallState
from brain.tools import ToolDispatcher
from brain.turn import Brain, UserTurn
from providers.llm.mock import MockLLM


def make_brain(scripted):
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    config = TenantConfigLoader(root).load("aura")
    clock = FixedClock(
        __import__("datetime").datetime(
            2026, 10, 25, 12, tzinfo=__import__("zoneinfo").ZoneInfo("Asia/Kolkata")
        )
    )
    state = CallState()
    dispatcher = ToolDispatcher(InMemoryOrderRepository(clock), state, config, clock.now)
    return Brain(config, state, MockLLM(scripted), dispatcher), state


def collect(brain, text):
    async def run():
        return [item async for item in brain.handle_turn(UserTurn(text))]

    return asyncio.run(run())


def test_order_id_confirmation_precedes_tool_round():
    brain, state = make_brain(
        [
            {
                "tool_call": {
                    "call_id": "1",
                    "name": "get_order_details",
                    "arguments": {"order_id": "ORD-101"},
                }
            },
            {"text": "It is out for delivery."},
        ]
    )
    first = collect(brain, "Where is ORD-101?")
    assert [item.kind for item in first] == ["SENTENCE", "DONE"]
    second = collect(brain, "yes")
    assert any(item.kind == "TOOL_RESULT" for item in second)
    assert state.confirmed_id == "ORD-101"
    tool_message = next(message for message in brain.messages if message["role"] == "tool")
    assert tool_message["tool_call_id"] == "1"


def test_cancel_requires_explicit_action_confirmation():
    brain, state = make_brain(
        [
            {
                "tool_call": {
                    "call_id": "1",
                    "name": "cancel_order",
                    "arguments": {"order_id": "ORD-103", "idempotency_key": "x"},
                }
            }
        ]
    )
    collect(brain, "Cancel ORD-103")
    collect(brain, "yes")
    assert state.pending_action == "cancel:ORD-103"
    result = collect(brain, "yes")
    assert any(
        "completed" in str(item.payload.get("text", ""))
        for item in result
        if item.kind == "SENTENCE"
    )


def test_multiple_tool_calls_share_one_assistant_message_and_matching_results():
    brain, state = make_brain([])
    state.confirmed_id = "ORD-101"

    class Provider:
        def __init__(self):
            self.requests = []

        async def generate(self, messages, tools, params):
            self.requests.append(list(messages))
            if len(self.requests) == 1:
                for call_id, name in [
                    ("lookup-1", "get_order_details"),
                    ("return-2", "check_return_eligibility"),
                ]:
                    yield {
                        "tool_call": {
                            "call_id": call_id,
                            "name": name,
                            "arguments": {"order_id": "ORD-101"},
                        }
                    }
            else:
                yield {"text": "The order is out for delivery."}

    provider = Provider()
    brain.llm = provider
    collect(brain, "Where is my order and can I return it?")
    history = provider.requests[-1]
    assistant = next(message for message in history if message["role"] == "assistant")
    results = [message for message in history if message["role"] == "tool"]
    assert [call["call_id"] for call in assistant["tool_calls"]] == ["lookup-1", "return-2"]
    assert [message["tool_call_id"] for message in results] == ["lookup-1", "return-2"]


def test_dispatch_rejects_non_tool_methods_and_malformed_model_output():
    brain, _ = make_brain([])
    assert brain._dispatch("__getattribute__", {"name": "state"})["ok"] is False
    assert brain._dispatch(None, {})["ok"] is False
    assert brain._dispatch("get_order_details", ["ORD-101"])["ok"] is False


def test_commit_spoken_truncates_history():
    brain, state = make_brain([{"text": "A short answer."}])
    collect(brain, "hello")
    brain.commit_spoken("A short")
    assert state.interrupted is True
    assert state.spoken_history[-1]["text"] == "A short"
