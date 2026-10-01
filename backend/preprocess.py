"""Compatibility CLI for causally imputing raw patient observations."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from .train_sepsis import load_patient_data

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_and_preprocess(
    data_dir: str | Path,
    limit: int | None = None,
) -> pd.DataFrame:
    """Load patient PSV files with within-patient forward fill and safe baselines."""
    return load_patient_data(data_dir, limit=limit)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=PROJECT_ROOT / "data")
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "data" / "cleaned_data_temporal.csv",
    )
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    cleaned = load_and_preprocess(args.data_dir, limit=args.limit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    cleaned.to_csv(args.output, index=False)
    print(
        f"Saved {cleaned.shape[0]} rows from "
        f"{cleaned['Patient_ID'].nunique()} patients to {args.output.resolve()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
