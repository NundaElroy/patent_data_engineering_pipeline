from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


def _is_bad_float(value: Any) -> bool:
    return isinstance(value, float) and (math.isnan(value) or math.isinf(value))


def to_json_safe(value: Any) -> Any:
    if _is_bad_float(value):
        return None

    if isinstance(value, dict):
        return {str(k): to_json_safe(v) for k, v in value.items()}

    if isinstance(value, list):
        return [to_json_safe(v) for v in value]

    return value


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rewrite reports/report.json to strict JSON (replace NaN/Infinity with null)."
    )
    parser.add_argument(
        "--input",
        default="reports/report.json",
        help="Path to report.json (default: reports/report.json)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output path. Default overwrites input.",
    )
    args = parser.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.output) if args.output else in_path

    if not in_path.exists():
        raise FileNotFoundError(f"Input file not found: {in_path}")

    with in_path.open("r", encoding="utf-8") as f:
        data = json.load(f)  # accepts NaN

    safe = to_json_safe(data)

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(safe, f, indent=2, ensure_ascii=False, allow_nan=False)
        f.write("\n")

    print(f"Wrote strict JSON: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
