from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker


class TenantConfigError(ValueError):
    pass


class TenantConfigLoader:
    def __init__(self, root: Path) -> None:
        self.root = root

    def load(self, tenant: str) -> dict[str, Any]:
        config_path = self.root / "apps" / "agent" / "tenants" / f"{tenant}.yaml"
        schema_path = self.root / "contracts" / "tenant_config.json"
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        errors = sorted(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(data), key=lambda e: list(e.path))
        if errors:
            raise TenantConfigError("; ".join(error.message for error in errors[:3]))
        return data
