from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml


def load_scenarios(root: Path) -> list[dict[str, Any]]:
    return [yaml.safe_load(path.read_text(encoding="utf-8")) for path in sorted((root / "evals" / "scenarios").glob("*.yaml"))]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["scripted", "live"], default="scripted")
    parser.add_argument("--max-calls", type=int, default=80)
    args = parser.parse_args()
    if args.mode == "live":
        raise SystemExit("Live mode is intentionally not implemented until the scripted suite passes and an explicit cap is approved.")
    root = Path(__file__).resolve().parents[2]
    scenarios = load_scenarios(root)
    print(f"loaded={len(scenarios)} mode=scripted quota_calls=0")


if __name__ == "__main__":
    main()
