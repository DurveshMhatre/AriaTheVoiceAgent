from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from brain.clock import FixedClock
from brain.ids import classify_yes_no, normalize_order_id
from brain.policy import cod_eligible, return_from_claim, shipping_fee
from brain.repo import InMemoryOrderRepository

IST = ZoneInfo("Asia/Kolkata")


def test_order_id_variants() -> None:
    variants = [
        "O R D one zero one",
        "order one oh one",
        "ord 101",
        "ORD-101",
        "o-r-d 1 0 1",
        "order zero one zero",
        "ord two five zero",
    ]
    assert all(normalize_order_id(value) for value in variants)
    assert normalize_order_id("book flight to Goa") is None
    assert normalize_order_id("ORD 12") is None


def test_confirmation_classifier() -> None:
    assert classify_yes_no("haan ji") is True
    assert classify_yes_no("nahi galat") is False
    assert classify_yes_no("maybe") is None


def test_literal_shipping_and_cod_boundaries() -> None:
    config = {
        "policies": {
            "free_shipping_threshold_inr": 499,
            "free_shipping_rule": "above",
            "shipping_fee_inr": 50,
            "cod_limit_inr": 2500,
            "cod_limit_inclusive": True,
        }
    }
    assert shipping_fee(499, config) == 50
    assert shipping_fee(500, config) == 0
    assert cod_eligible(2500, config) is True
    assert cod_eligible(2501, config) is False


def test_claim_return_day_boundaries() -> None:
    config = {"policies": {"return_window_days": 7}}
    assert return_from_claim(7, False, config).decision == "ELIGIBLE"
    assert return_from_claim(7.0001, False, config).decision == "INELIGIBLE"
    assert return_from_claim(1, True, config).reason_codes == ("ITEM_OPENED",)


def test_relative_orders() -> None:
    clock = FixedClock(datetime(2026, 10, 25, 12, tzinfo=IST))
    repo = InMemoryOrderRepository(clock)
    assert repo.get("ORD-102").delivered_at == clock.now() - timedelta(days=14)
