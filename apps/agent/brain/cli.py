from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from .clock import SystemClock
from .config import TenantConfigLoader
from .repo import InMemoryOrderRepository
from .state import CallState
from .tools import ToolDispatcher
from .turn import Brain, UserTurn
from providers.llm.mock import MockLLM


async def run(tenant: str) -> None:
    root = Path(__file__).resolve().parents[3]
    config = TenantConfigLoader(root).load(tenant)
    clock = SystemClock()
    state = CallState()
    dispatcher = ToolDispatcher(InMemoryOrderRepository(clock), state, config, clock.now)
    brain = Brain(config, state, MockLLM(), dispatcher)
    print("Aria text mode. Type /quit to exit.")
    while True:
        text = input("You: ")
        if text == "/quit":
            break
        if text == "/state":
            print(state.as_dict())
            continue
        async for item in brain.handle_turn(UserTurn(text)):
            if item.kind in {"FILLER", "SENTENCE"}:
                print(f"Aria: {item.payload['text']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant", default="aura")
    args = parser.parse_args()
    asyncio.run(run(args.tenant))
