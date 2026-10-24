from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from .clock import SystemClock
from .config import TenantConfigLoader
from .repo import InMemoryOrderRepository
from .state import CallState
from .summary import deterministic_summary
from .tools import ToolDispatcher
from .turn import Brain, UserTurn
from providers.llm.factory import create_llm


async def run(tenant: str, llm_mode: str) -> None:
    root = Path(__file__).resolve().parents[3]
    config = TenantConfigLoader(root).load(tenant)
    clock = SystemClock()
    state = CallState()
    repo = InMemoryOrderRepository(clock)
    dispatcher = ToolDispatcher(repo, state, config, clock.now)
    brain = Brain(config, state, create_llm(llm_mode), dispatcher)
    events: list[dict[str, object]] = []
    print("Aria text mode. Commands: /state /events /summary /usage /orders /reset /quit")
    while True:
        try:
            text = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if text == "/quit":
            break
        if text == "/state":
            print(json.dumps(state.as_dict(), indent=2, default=str))
            continue
        if text == "/events":
            print(json.dumps(events, indent=2, default=str))
            continue
        if text == "/summary":
            print(json.dumps(deterministic_summary(state), indent=2))
            continue
        if text == "/usage":
            print(json.dumps(state.usage, indent=2))
            continue
        if text == "/orders":
            for order_id in ("ORD-101", "ORD-102", "ORD-103"):
                order = repo.get(order_id)
                print(json.dumps({"order_id": order.order_id, "product": order.product, "value_inr": order.value_inr, "status": order.status, "tracking_id": order.tracking_id, "expected_note": order.expected_note}, default=str))
            continue
        if text == "/reset":
            state.reset()
            brain.messages.clear()
            events.clear()
            print("Reset complete.")
            continue
        async for item in brain.handle_turn(UserTurn(text)):
            events.append({"kind": item.kind, "payload": item.payload})
            if item.kind in {"FILLER", "SENTENCE"}:
                print(f"Aria: {item.payload['text']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant", default="aura")
    parser.add_argument("--llm", choices=["mock", "gemini", "groq", "auto"], default="mock")
    args = parser.parse_args()
    asyncio.run(run(args.tenant, args.llm))
