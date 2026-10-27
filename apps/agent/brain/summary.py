from __future__ import annotations

from typing import Any

from .state import CallState


def deterministic_summary(
    state: CallState, prose: str = "The conversation was recorded."
) -> dict[str, Any]:
    status = (
        "ESCALATED"
        if state.escalation_flag
        else ("PARTIALLY_RESOLVED" if state.tool_results else "UNRESOLVED")
    )
    return {
        "schema_version": 1,
        "customer_intent": state.intent,
        "order_id": state.confirmed_id,
        "resolution_status": status,
        "policy_outcome": None,
        "call_summary": prose[:1000],
        "follow_up_needed": state.escalation_flag,
    }
