from __future__ import annotations

import re

_DIGITS = {"zero":"0","oh":"0","o":"0","one":"1","two":"2","three":"3","four":"4","five":"5","six":"6","seven":"7","eight":"8","nine":"9"}


def normalize_order_id(text: str, id_format: str = "ORD-###") -> str | None:
    raw = text.strip().lower()
    if not raw:
        return None
    compact = re.sub(r"[^a-z0-9]", "", raw)
    direct = re.fullmatch(r"ord(\d{3})", compact)
    if direct:
        return f"ORD-{direct.group(1)}"
    tokens = re.findall(r"[a-z]+|\d+", raw)
    if tokens and tokens[0] in {"order", "ord"}:
        tokens = tokens[1:]
    digits: list[str] = []
    for token in tokens:
        if token.isdigit() and len(token) == 3:
            digits.extend(token)
        elif token in _DIGITS:
            digits.append(_DIGITS[token])
        else:
            return None
    if len(digits) == 3:
        return f"ORD-{''.join(digits)}"
    return None


def classify_yes_no(text: str) -> bool | None:
    tokens = set(re.findall(r"[a-z]+", text.lower()))
    yes = {"yes", "yeah", "yep", "haan", "han", "ji", "correct", "confirm", "confirmed"}
    no = {"no", "nope", "nahi", "nahin", "wrong", "galat", "incorrect"}
    if tokens & yes and not tokens & no:
        return True
    if tokens & no and not tokens & yes:
        return False
    return None
