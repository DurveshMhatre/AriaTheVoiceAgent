from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "agent"))

from brain.clock import FixedClock  # noqa: E402
from brain.config import TenantConfigLoader  # noqa: E402
from brain.repo import InMemoryOrderRepository  # noqa: E402
from brain.state import CallState  # noqa: E402
from brain.tools import ToolDispatcher  # noqa: E402
from brain.turn import Brain, UserTurn  # noqa: E402
from providers.llm.mock import MockLLM  # noqa: E402


def load_scenarios(root: Path) -> list[dict[str, Any]]:
    path = root / "evals" / "scenarios" / "core.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


async def run_one(config: dict[str, Any], scenario: dict[str, Any]) -> dict[str, Any]:
    clock = FixedClock(__import__("datetime").datetime(2026, 10, 25, 12, tzinfo=__import__("zoneinfo").ZoneInfo("Asia/Kolkata")))
    state = CallState()
    dispatcher = ToolDispatcher(InMemoryOrderRepository(clock), state, config, clock.now)
    brain = Brain(config, state, MockLLM(scenario.get("mock_llm", [])), dispatcher)
    sentences: list[str] = []
    tool_names: list[str] = []
    events: list[dict[str, Any]] = []
    for text in scenario["user_turns"]:
        async for item in brain.handle_turn(UserTurn(text)):
            events.append({"kind": item.kind, "payload": item.payload})
            if item.kind == "SENTENCE":
                sentences.append(str(item.payload["text"]))
            if item.kind == "TOOL_CALL":
                tool_names.append(str(item.payload.get("name", "")))
    combined = " ".join(sentences).lower()
    assertions = scenario.get("assertions", {})
    failures: list[str] = []
    for phrase in assertions.get("required_phrases", []):
        if phrase.lower() not in combined:
            failures.append(f"missing required phrase: {phrase}")
    for phrase in assertions.get("forbidden_phrases", []):
        if phrase.lower() in combined:
            failures.append(f"forbidden phrase present: {phrase}")
    expected_tools = assertions.get("expected_tools", [])
    for name in expected_tools:
        if name not in tool_names:
            failures.append(f"missing tool call: {name}")
    return {"id": scenario["id"], "passed": not failures, "failures": failures, "tools": tool_names, "transcript": sentences, "events": events}


async def main_async(mode: str, max_calls: int) -> int:
    if mode == "live":
        print("live mode is intentionally blocked in the scripted runner; use a separately approved capped live command")
        return 2
    config = TenantConfigLoader(ROOT).load("aura")
    scenarios = load_scenarios(ROOT)
    results = [await run_one(config, item) for item in scenarios]
    passed = sum(1 for item in results if item["passed"])
    for item in results:
        status = "PASS" if item["passed"] else "FAIL"
        detail = "; ".join(item["failures"])
        print(f"{status} {item['id']} tools={','.join(item['tools']) or '-'} {detail}".rstrip())
    print(f"SUMMARY mode=scripted passed={passed} failed={len(results) - passed} total={len(results)} quota_calls=0 max_calls={max_calls}")
    result_dir = ROOT / "evals" / "results"
    result_dir.mkdir(parents=True, exist_ok=True)
    (result_dir / "scripted-latest.json").write_text(__import__("json").dumps(results, indent=2), encoding="utf-8")
    return 0 if passed == len(results) else 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["scripted", "live"], default="scripted")
    parser.add_argument("--max-calls", type=int, default=80)
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main_async(args.mode, args.max_calls)))


if __name__ == "__main__":
    main()
