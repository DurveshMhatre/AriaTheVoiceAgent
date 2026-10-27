from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from .repo import Order


@dataclass(frozen=True)
class PolicyDecision:
    decision: str
    reason_codes: tuple[str, ...]
    basis: str
    missing: tuple[str, ...] = ()
    allowed_actions: tuple[str, ...] = ()


def shipping_fee(value_inr: int, config: dict[str, Any]) -> int:
    threshold = config["policies"]["free_shipping_threshold_inr"]
    rule = config["policies"]["free_shipping_rule"]
    free = value_inr > threshold if rule == "above" else value_inr >= threshold
    return 0 if free else config["policies"]["shipping_fee_inr"]


def cod_eligible(value_inr: int, config: dict[str, Any]) -> bool:
    policy = config["policies"]
    limit = int(policy["cod_limit_inr"])
    inclusive = bool(policy["cod_limit_inclusive"])
    return (
        value_inr <= limit
        if inclusive
        else value_inr < limit
    )


def return_from_order(
    order: Order,
    now: datetime,
    opened: bool | None,
    config: dict[str, Any],
    issue_type: str = "CHANGE_OF_MIND",
) -> PolicyDecision:
    if issue_type == "DAMAGED_OR_DEFECTIVE":
        if order.delivered_at is None:
            return PolicyDecision(
                "NOT_APPLICABLE_YET",
                ("NOT_YET_DELIVERED",),
                "ORDER_RECORD",
                allowed_actions=("REFUSE_DELIVERY",),
            )
        within = now - order.delivered_at <= timedelta(
            hours=config["policies"]["damage_report_window_hours"]
        )
        return PolicyDecision(
            "ELIGIBLE" if within else "INELIGIBLE",
            ("DAMAGE_WINDOW_OPEN" if within else "DAMAGE_WINDOW_EXPIRED",),
            "ORDER_RECORD",
            allowed_actions=("REPORT_WITH_PHOTOS_THROUGH_SUPPORT",) if within else (),
        )
    if order.delivered_at is None:
        action = "CANCEL" if order.status == "Processing" else "REFUSE_DELIVERY"
        return PolicyDecision(
            "NOT_APPLICABLE_YET", ("NOT_YET_DELIVERED",), "ORDER_RECORD", allowed_actions=(action,)
        )
    if now - order.delivered_at > timedelta(days=config["policies"]["return_window_days"]):
        return PolicyDecision("INELIGIBLE", ("RETURN_WINDOW_EXPIRED",), "ORDER_RECORD")
    if opened is None:
        return PolicyDecision(
            "NEEDS_INFO", ("OPENED_STATUS_REQUIRED",), "ORDER_RECORD", missing=("opened",)
        )
    if opened:
        return PolicyDecision("INELIGIBLE", ("ITEM_OPENED",), "ORDER_RECORD")
    return PolicyDecision(
        "ELIGIBLE", ("RETURN_ELIGIBLE",), "ORDER_RECORD", allowed_actions=("START_RETURN_REQUEST",)
    )


def return_from_claim(
    days_since_delivery: float, opened: bool, config: dict[str, Any]
) -> PolicyDecision:
    if opened:
        return PolicyDecision("INELIGIBLE", ("ITEM_OPENED",), "CUSTOMER_CLAIM")
    return PolicyDecision(
        "ELIGIBLE"
        if days_since_delivery <= config["policies"]["return_window_days"]
        else "INELIGIBLE",
        (
            "RETURN_ELIGIBLE"
            if days_since_delivery <= config["policies"]["return_window_days"]
            else "RETURN_WINDOW_EXPIRED",
        ),
        "CUSTOMER_CLAIM",
    )


def cancellation(order: Order) -> PolicyDecision:
    if order.status == "Processing":
        return PolicyDecision(
            "ELIGIBLE", ("CANCEL_ALLOWED",), "ORDER_RECORD", allowed_actions=("CANCEL",)
        )
    if order.status in {"Shipped", "Out for Delivery"}:
        return PolicyDecision(
            "INELIGIBLE",
            ("CANCEL_BLOCKED_SHIPPED",),
            "ORDER_RECORD",
            allowed_actions=("REFUSE_DELIVERY",),
        )
    return PolicyDecision(
        "INELIGIBLE",
        ("CANCEL_BLOCKED_DELIVERED",),
        "ORDER_RECORD",
        allowed_actions=("CHECK_RETURN_POLICY",),
    )
