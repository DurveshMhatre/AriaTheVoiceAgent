"""Validate Phase 0 contracts and all representative samples.

Dependencies are intentionally limited to jsonschema and PyYAML.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
import yaml

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "contracts"
SAMPLES = CONTRACTS / "samples"


def load_json(path: Path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def validate(schema_path: Path, instance, label: str) -> None:
    schema = load_json(schema_path)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(instance), key=lambda error: list(error.path))
    if errors:
        messages = "; ".join(error.message for error in errors[:3])
        raise AssertionError(f"{label} should be valid: {messages}")


def rejects(schema_path: Path, instance, label: str) -> None:
    schema = load_json(schema_path)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    if validator.is_valid(instance):
        raise AssertionError(f"{label} should be rejected")


def main() -> int:
    mapping = {
        "tool_schemas": CONTRACTS / "tool_schemas.json",
        "call_events": CONTRACTS / "call_events.json",
        "call_summary": CONTRACTS / "call_summary.json",
        "tenant_config": CONTRACTS / "tenant_config.json",
    }
    passed = 0
    for name, schema_path in mapping.items():
        for sample in sorted((SAMPLES / "valid").glob(f"{name}_*.json")):
            validate(schema_path, load_json(sample), str(sample.relative_to(ROOT)))
            print(f"PASS valid {sample.relative_to(ROOT)}")
            passed += 1
        for sample in sorted((SAMPLES / "invalid").glob(f"{name}_*.json")):
            rejects(schema_path, load_json(sample), str(sample.relative_to(ROOT)))
            print(f"PASS rejected {sample.relative_to(ROOT)}")
            passed += 1

    aura_path = ROOT / "apps" / "agent" / "tenants" / "aura.yaml"
    aura = yaml.safe_load(aura_path.read_text(encoding="utf-8"))
    validate(mapping["tenant_config"], aura, str(aura_path.relative_to(ROOT)))
    print(f"PASS valid {aura_path.relative_to(ROOT)}")
    passed += 1
    print(f"SUMMARY {passed} checks passed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        raise SystemExit(1)
