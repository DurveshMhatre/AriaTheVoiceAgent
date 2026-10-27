from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from brain.clock import FixedClock
from brain.config import TenantConfigLoader
from brain.repo import InMemoryOrderRepository
from brain.state import CallState
from brain.tools import ToolDispatcher


def _dispatcher() -> ToolDispatcher:
    root = Path(__file__).resolve().parents[3]
    config = TenantConfigLoader(root).load("aura")
    now = datetime(2026, 10, 26, 12, tzinfo=ZoneInfo("Asia/Kolkata"))
    clock = FixedClock(now)
    state = CallState()
    return ToolDispatcher(InMemoryOrderRepository(clock), state, config, clock.now)


def test_order_lookup_validation_confirmation_and_missing_record() -> None:
    tools = _dispatcher()
    assert tools.get_order_details("not an id")["error_code"] == "INVALID_FORMAT"
    assert tools.get_order_details("ORD-101")["error_code"] == "ID_NOT_CONFIRMED"
    tools.state.confirmed_id = "ORD-999"
    assert tools.get_order_details("ORD-999")["error_code"] == "NOT_FOUND"
    tools.state.confirmed_id = "ORD-101"
    result = tools.get_order_details("ORD-101")
    assert result["ok"] is True and result["data"]["status"] == "Out for Delivery"


def test_return_tool_order_claim_and_argument_paths() -> None:
    tools = _dispatcher()
    assert tools.check_return_eligibility()["error_code"] == "MISSING_ARGUMENT"
    assert tools.check_return_eligibility(order_id="ORD 101")["error_code"] == "ID_NOT_CONFIRMED"
    tools.state.confirmed_id = "ORD-999"
    assert tools.check_return_eligibility(order_id="ORD-999")["error_code"] == "NOT_FOUND"
    tools.state.confirmed_id = "ORD-102"
    result = tools.check_return_eligibility(order_id="ORD-102", opened=False)
    assert result["ok"] is True and result["data"]["decision"] == "INELIGIBLE"
    claim = tools.check_return_eligibility(days_since_delivery=7, opened=False)
    assert claim["data"]["decision"] == "ELIGIBLE"


def test_cancel_confirmation_eligibility_and_idempotency() -> None:
    tools = _dispatcher()
    assert tools.cancel_order("bad", "key")["error_code"] == "INVALID_FORMAT"
    assert tools.cancel_order("ORD-103", "key")["error_code"] == "ID_NOT_CONFIRMED"
    tools.state.confirmed_id = "ORD-103"
    assert tools.cancel_order("ORD-103", "key")["error_code"] == "MISSING_ARGUMENT"
    tools.state.pending_action = "cancel:ORD-103"
    assert tools.cancel_order("ORD-103", "key")["data"]["cancelled"] is True
    assert tools.cancel_order("ORD-103", "key")["data"]["already_cancelled"] is True
    tools.state.confirmed_id = "ORD-101"
    tools.state.pending_action = "cancel:ORD-101"
    refused = tools.cancel_order("ORD-101", "another")
    assert refused["error_code"] == "NOT_ELIGIBLE"
    assert "refuse delivery" in refused["speakable_hint"].lower()
    tools.state.confirmed_id = "ORD-999"
    tools.state.pending_action = "cancel:ORD-999"
    assert tools.cancel_order("ORD-999", "missing")["error_code"] == "NOT_FOUND"


def test_escalation_reason_validation_and_ticket_record() -> None:
    tools = _dispatcher()
    assert tools.escalate_to_human("guess")["error_code"] == "INVALID_FORMAT"
    result = tools.escalate_to_human("CUSTOMER_REQUEST", "customer requested a person")
    assert result["ok"] is True
    assert tools.tickets == [{"reason": "CUSTOMER_REQUEST", "note": "customer requested a person"}]
