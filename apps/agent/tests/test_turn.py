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
    clock = FixedClock(__import__("datetime").datetime(2026, 10, 25, 12, tzinfo=__import__("zoneinfo").ZoneInfo("Asia/Kolkata")))
    state = CallState()
    dispatcher = ToolDispatcher(InMemoryOrderRepository(clock), state, config, clock.now)
    return Brain(config, state, MockLLM(scripted), dispatcher), state


def collect(brain, text):
    async def run():
        return [item async for item in brain.handle_turn(UserTurn(text))]
    return asyncio.run(run())


def test_order_id_confirmation_precedes_tool_round():
    brain, state = make_brain([{"tool_call": {"call_id": "1", "name": "get_order_details", "arguments": {"order_id": "ORD-101"}}}, {"text": "It is out for delivery."}])
    first = collect(brain, "Where is ORD-101?")
    assert [item.kind for item in first] == ["SENTENCE", "DONE"]
    second = collect(brain, "yes")
    assert any(item.kind == "TOOL_RESULT" for item in second)
    assert state.confirmed_id == "ORD-101"


def test_cancel_requires_explicit_action_confirmation():
    brain, state = make_brain([{"tool_call": {"call_id": "1", "name": "cancel_order", "arguments": {"order_id": "ORD-103", "idempotency_key": "x"}}}])
    collect(brain, "Cancel ORD-103")
    collect(brain, "yes")
    assert state.pending_action == "cancel:ORD-103"
    result = collect(brain, "yes")
    assert any("completed" in str(item.payload.get("text", "")) for item in result if item.kind == "SENTENCE")


def test_commit_spoken_truncates_history():
    brain, state = make_brain([{ "text": "A short answer." }])
    collect(brain, "hello")
    brain.commit_spoken("A short")
    assert state.interrupted is True
    assert state.spoken_history[-1]["text"] == "A short"
