from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from brain.clock import FixedClock
from brain.guardrails import validate_output
from brain.policy import cancellation, return_from_order
from brain.repo import InMemoryOrderRepository, Order
from brain.state import CallState


def _setup() -> tuple[dict[str, object], InMemoryOrderRepository, datetime]:
    now = datetime(2026, 10, 26, 12, tzinfo=ZoneInfo("Asia/Kolkata"))
    config: dict[str, object] = {
        "policies": {
            "return_window_days": 7,
            "damage_report_window_hours": 48,
        }
    }
    return config, InMemoryOrderRepository(FixedClock(now)), now


def test_policy_order_return_all_evidence_branches() -> None:
    config, repository, now = _setup()
    undelivered = repository.get("ORD-103")
    delivered = repository.get("ORD-102")
    assert undelivered is not None and delivered is not None

    assert return_from_order(undelivered, now, False, config).allowed_actions == ("CANCEL",)
    assert return_from_order(delivered, now, None, config).decision == "INELIGIBLE"
    recent = Order(**{**delivered.__dict__, "delivered_at": now - timedelta(days=7)})
    assert return_from_order(recent, now, None, config).decision == "NEEDS_INFO"
    assert return_from_order(recent, now, True, config).reason_codes == ("ITEM_OPENED",)
    eligible = return_from_order(recent, now, False, config)
    assert eligible.allowed_actions == ("START_RETURN_REQUEST",)
    not_delivered = return_from_order(
        undelivered, now, False, config, "DAMAGED_OR_DEFECTIVE"
    )
    assert not_delivered.decision == "NOT_APPLICABLE_YET"
    damaged = Order(**{**delivered.__dict__, "delivered_at": now - timedelta(hours=24)})
    expired_damage = return_from_order(delivered, now, False, config, "DAMAGED_OR_DEFECTIVE")
    open_damage = return_from_order(damaged, now, False, config, "DAMAGED_OR_DEFECTIVE")
    assert expired_damage.reason_codes == ("DAMAGE_WINDOW_EXPIRED",)
    assert open_damage.allowed_actions == ("REPORT_WITH_PHOTOS_THROUGH_SUPPORT",)


def test_cancellation_status_decisions() -> None:
    config, repository, _ = _setup()
    processing = repository.get("ORD-103")
    shipping = repository.get("ORD-101")
    delivered = repository.get("ORD-102")
    assert processing and shipping and delivered
    assert cancellation(processing).allowed_actions == ("CANCEL",)
    assert cancellation(shipping).allowed_actions == ("REFUSE_DELIVERY",)
    assert cancellation(delivered).allowed_actions == ("CHECK_RETURN_POLICY",)


def test_call_state_confirmation_escalation_reset_and_serialization() -> None:
    state = CallState()
    state.set_candidate("ORD-101")
    state.confirm_candidate(True)
    assert state.confirmed_id == "ORD-101"
    state.confirm_candidate(False)
    state.confirm_candidate(None)
    assert state.id_attempts == 2 and state.escalation_flag
    state.record_unclear()
    state.record_unclear()
    state.record_unclear()
    state.commit_spoken("t1", "partial")
    state.tool_results.append({"ok": True})
    assert state.as_dict()["spoken_history"] == [{"turn_id": "t1", "text": "partial"}]
    state.reset()
    assert state.candidate_id is None and state.confirmed_id is None
    assert state.spoken_history == [] and state.tool_results == []
    assert state.usage == {"calls": 0, "input_tokens": 0, "output_tokens": 0, "latency_ms": 0}


def test_guardrail_rewrites_promises_strips_urls_and_limits_sentences() -> None:
    config: dict[str, object] = {}
    promise = validate_output("Refund approved.", config)
    assert promise.triggered and "refund approved" not in promise.text.lower()
    result = validate_output("Hello **there** https://example.test. One. Two.", config)
    assert result.triggered
    assert "https://" not in result.text and "**" not in result.text
    assert result.reasons == ("URL_REMOVED", "SENTENCE_LIMIT")
    detail = validate_output("One. Two. Three.", config, detail_requested=True)
    assert detail.text.count(".") == 3
    escalated = validate_output("I can help.", config, escalation=True)
    assert "support team" in escalated.text and "ESCALATION_OFFER" in escalated.reasons


def test_text_cli_handles_local_commands(monkeypatch, capsys) -> None:
    from brain.cli import run

    inputs = iter(["/orders", "/state", "/events", "/summary", "/usage", "/reset", "/quit"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))
    asyncio.run(run("aura", "mock"))
    output = capsys.readouterr().out
    assert "ORD-101" in output and "ORD-102" in output and "ORD-103" in output
    assert "Reset complete." in output
