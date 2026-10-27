import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from brain.clock import FixedClock
from brain.repo import InMemoryOrderRepository


def test_test_orders_fixture_matches_brain_seed() -> None:
    root = Path(__file__).resolve().parents[3]
    fixture_path = root / "apps/web/src/fixtures/test_orders.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    clock = FixedClock(datetime(2026, 10, 26, 12, tzinfo=ZoneInfo("Asia/Kolkata")))
    repository = InMemoryOrderRepository(clock)
    assert len(fixture) == 3
    for item in fixture:
        order = repository.get(item["order_id"])
        assert order is not None
        assert item["value_inr"] == order.value_inr
        assert item["status"] == order.status
