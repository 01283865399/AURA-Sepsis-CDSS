"""Validate medical content integrity and report governed coverage targets."""

from __future__ import annotations

import json
from pathlib import Path

from data.medical_content.validator import validate_content_dir


def main() -> int:
    content_dir = Path(__file__).resolve().parents[1] / "data" / "medical_content"
    report = validate_content_dir(content_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
