from brain.guardrails import validate_output


def test_promise_is_blocked() -> None:
    result = validate_output("Your refund is approved and I will process it.", {})
    assert result.triggered is True
    assert "approved" not in result.text.lower()


def test_long_reply_is_limited() -> None:
    result = validate_output("One. Two. Three.", {})
    assert result.text.count(".") <= 2


def test_escalation_offer_is_added() -> None:
    result = validate_output("I do not have that information.", {}, escalation=True)
    assert "support team" in result.text.lower()
