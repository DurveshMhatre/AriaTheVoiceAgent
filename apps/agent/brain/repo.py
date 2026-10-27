from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from .clock import Clock


@dataclass(frozen=True)
class Order:
    order_id: str
    product: str
    value_inr: int
    status: str
    carrier: str | None
    tracking_id: str | None
    expected_note: str | None
    ordered_at: datetime
    delivered_at: datetime | None


class OrderRepository(Protocol):
    def get(self, order_id: str) -> Order | None: ...


class InMemoryOrderRepository:
    def __init__(self, clock: Clock) -> None:
        now = clock.now()
        self._orders = {
            "ORD-101": Order(
                "ORD-101",
                "Vitamin C Serum (30ml)",
                699,
                "Out for Delivery",
                "BlueDart",
                "BD-982103",
                "expected by 6 PM today",
                now - timedelta(hours=3),
                None,
            ),
            "ORD-102": Order(
                "ORD-102",
                "Hydrating Sunscreen SPF 50",
                499,
                "Delivered",
                "Delhivery",
                "DL-441029",
                "delivered 14 days ago",
                now - timedelta(days=20),
                now - timedelta(days=14),
            ),
            "ORD-103": Order(
                "ORD-103",
                "Green Tea Face Wash + Toner",
                850,
                "Processing",
                None,
                None,
                "ordered 3 hours ago",
                now - timedelta(hours=3),
                None,
            ),
        }

    def get(self, order_id: str) -> Order | None:
        return self._orders.get(order_id)
