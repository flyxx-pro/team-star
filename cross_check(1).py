"""Standalone Cross-check entry.

The same logic is called inside run_week6_pipeline.py. This wrapper is kept so
reviewers can run only the validation step when they want to inspect the three
Final/Auto tables without rebuilding the whole package.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Regenerate validation/cross_check.csv from Auto tables.")
    parser.add_argument("--root", default=".", help="Repository root.")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    sys.path.insert(0, str(root / "pipeline"))

    from run_week6_pipeline import build_cross_check, read_csv_dict, write_csv

    subscription = read_csv_dict(root / "auto_output" / "subscription_auto.csv")
    snapshot = read_csv_dict(root / "auto_output" / "equity_snapshot_auto.csv")
    rows = build_cross_check(subscription, snapshot)
    write_csv(root / "validation" / "cross_check.csv", rows, ["check_type", "stock_code", "record_id", "status", "metric", "detail"])
    print(f"cross_check_rows={len(rows)}")


if __name__ == "__main__":
    main()
