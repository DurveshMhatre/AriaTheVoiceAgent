from __future__ import annotations

import re

_DIGITS = {
    "zero": "0",
    "oh": "0",
    "o": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
}


def normalize_order_id(text: str, id_format: str = "ORD-###") -> str | None:
    raw = text.strip().lower()
    if not raw:
        return None

    candidates: list[str] = []
    direct_ids = re.findall(r"(?<![a-z0-9])(?:order|ord)[\s-]*(\d{3})(?!\d)", raw)
    candidates.extend(direct_ids)

    tokens = re.findall(r"[a-z]+|\d+", raw)
    prefixes: list[int] = []
    for index, token in enumerate(tokens):
        if token in {"order", "ord"}:
            prefixes.append(index)
        elif tokens[index : index + 3] == ["o", "r", "d"]:
            prefixes.append(index + 2)

    for prefix in prefixes:
        digits: list[str] = []
        for token in tokens[prefix + 1 :]:
            if token.isdigit():
                if len(token) == 3 and not digits:
                    digits.extend(token)
                elif len(token) == 1:
                    digits.append(token)
                else:
                    break
            elif token in _DIGITS:
                digits.append(_DIGITS[token])
            else:
                break
            if len(digits) >= 3:
                break
        if len(digits) == 3:
            candidates.append("".join(digits))

    unique = set(candidates)
    if len(unique) != 1:
        return None
    return f"ORD-{unique.pop()}"


def classify_yes_no(text: str) -> bool | None:
    tokens = set(re.findall(r"[a-z]+", text.lower()))
    yes = {"yes", "yeah", "yep", "haan", "han", "ji", "correct", "confirm", "confirmed"}
    no = {"no", "nope", "nahi", "nahin", "wrong", "galat", "incorrect"}
    if tokens & yes and not tokens & no:
        return True
    if tokens & no and not tokens & yes:
        return False
    return None
