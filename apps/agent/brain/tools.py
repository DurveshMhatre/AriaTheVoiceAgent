from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from .ids import normalize_order_id
from .policy import cancellation, return_from_claim, return_from_order
from .repo import InMemoryOrderRepository
from .state import CallState


def result(
    ok: bool, data: Any = None, error_code: str | None = None, speakable_hint: str | None = None
) -> dict[str, Any]:
    return {"ok": ok, "data": data, "error_code": error_code, "speakable_hint": speakable_hint}


class ToolDispatcher:
    def __init__(
        self,
        repo: InMemoryOrderRepository,
        state: CallState,
        config: dict[str, Any],
        now: Callable[[], datetime],
    ) -> None:
        self.repo, self.state, self.config, self.now = repo, state, config, now
        self.tickets: list[dict[str, str]] = []
        self.cancelled: set[str] = set()

    def _confirmed(self, order_id: str) -> bool:
        return (
            self.config["policies"].get("id_confirmation", "always") == "never"
            or self.state.confirmed_id == order_id
        )

    def get_order_details(self, order_id: str) -> dict[str, Any]:
        normalized = normalize_order_id(order_id)
        if normalized is None:
            return result(
                False, error_code="INVALID_FORMAT", speakable_hint="Please repeat the order ID."
            )
        if not self._confirmed(normalized):
            return result(
                False,
                error_code="ID_NOT_CONFIRMED",
                speakable_hint="Please confirm the order ID first.",
            )
        order = self.repo.get(normalized)
        if order is None:
            return result(
                False, error_code="NOT_FOUND", speakable_hint="I could not find that order."
            )
        return result(
            True,
            data={
                "order_id": order.order_id,
                "product": order.product,
                "value_inr": order.value_inr,
                "status": order.status,
                "carrier": order.carrier,
                "tracking_id": order.tracking_id,
                "expected_note": order.expected_note,
            },
        )

    def check_return_eligibility(self, **kwargs: Any) -> dict[str, Any]:
        issue_type = kwargs.get("issue_type", "CHANGE_OF_MIND")
        order_id = kwargs.get("order_id")
        if order_id is not None:
            normalized = normalize_order_id(str(order_id))
            if normalized is None:
                return result(
                    False, error_code="INVALID_FORMAT", speakable_hint="Please repeat the order ID."
                )
            if not self._confirmed(normalized):
                return result(
                    False,
                    error_code="ID_NOT_CONFIRMED",
                    speakable_hint="Please confirm the order ID first.",
                )
            order = self.repo.get(normalized)
            if order is None:
                return result(
                    False, error_code="NOT_FOUND", speakable_hint="I could not find that order."
                )
            decision = return_from_order(
                order, self.now(), kwargs.get("opened"), self.config, issue_type
            )
        elif "days_since_delivery" in kwargs and "opened" in kwargs:
            decision = return_from_claim(
                float(kwargs["days_since_delivery"]), bool(kwargs["opened"]), self.config
            )
        else:
            return result(
                False,
                error_code="MISSING_ARGUMENT",
                speakable_hint="I need an order ID or delivery timing.",
            )
        return result(
            True,
            data={
                "decision": decision.decision,
                "reason_codes": list(decision.reason_codes),
                "basis": decision.basis,
                "missing": list(decision.missing),
                "allowed_actions": list(decision.allowed_actions),
            },
        )

    def cancel_order(self, order_id: str, idempotency_key: str) -> dict[str, Any]:
        normalized = normalize_order_id(order_id)
        if normalized is None:
            return result(
                False, error_code="INVALID_FORMAT", speakable_hint="Please repeat the order ID."
            )
        if not self._confirmed(normalized):
            return result(
                False,
                error_code="ID_NOT_CONFIRMED",
                speakable_hint="Please confirm the order ID first.",
            )
        if self.state.pending_action != f"cancel:{normalized}":
            self.state.pending_action = f"cancel:{normalized}"
            return result(
                False,
                error_code="MISSING_ARGUMENT",
                speakable_hint="Please confirm that you want to cancel it.",
            )
        order = self.repo.get(normalized)
        if order is None:
            return result(
                False, error_code="NOT_FOUND", speakable_hint="I could not find that order."
            )
        decision = cancellation(order)
        if decision.decision != "ELIGIBLE":
            hint = "This order cannot be cancelled now."
            if "REFUSE_DELIVERY" in decision.allowed_actions:
                hint += " You may refuse delivery at the doorstep."
            elif "CHECK_RETURN_POLICY" in decision.allowed_actions:
                hint += " I can check the return policy for you."
            return result(
                False,
                data={
                    "reason_codes": list(decision.reason_codes),
                    "allowed_actions": list(decision.allowed_actions),
                },
                error_code="NOT_ELIGIBLE",
                speakable_hint=hint,
            )
        if idempotency_key in self.cancelled:
            return result(True, data={"order_id": normalized, "already_cancelled": True})
        self.cancelled.add(idempotency_key)
        return result(True, data={"order_id": normalized, "cancelled": True})

    def escalate_to_human(self, reason: str, note: str = "") -> dict[str, Any]:
        allowed = {
            "CUSTOMER_REQUEST",
            "FRUSTRATION",
            "REPEATED_FAILURE",
            "UNKNOWN_INFORMATION",
            "OTHER",
        }
        if reason not in allowed:
            return result(
                False,
                error_code="INVALID_FORMAT",
                speakable_hint="I can record a support follow-up.",
            )
        self.tickets.append({"reason": reason, "note": note})
        return result(
            True, data={"ticket_recorded": True}, speakable_hint="The support team will follow up."
        )
