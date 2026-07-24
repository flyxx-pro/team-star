"""Unified Week 6 entry point.

Run from the repository root:
    python pipeline/run_all.py --root .

The automatic extraction step never reads manual_gold/ or final/ before
creating Auto tables. Manual Gold and Final are generated in a second layer
to document review decisions and teacher-facing deliverables.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def run_python(script: Path, root: Path, *args: str) -> None:
    subprocess.run(
        [sys.executable, str(script), "--root", str(root), *args],
        cwd=root,
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Week 6 extraction, curation and validation.")
    parser.add_argument("--root", default=".", help="Repository root. Use a relative path when possible.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    pipeline_dir = root / "pipeline"

    run_python(pipeline_dir / "run_week6_pipeline.py", root)
    run_python(pipeline_dir / "curate_final_and_report.py", root)

    # Run the automatic step again after Gold exists so Auto-vs-Gold can be
    # regenerated without making Auto depend on Gold.
    run_python(pipeline_dir / "run_week6_pipeline.py", root)

    prepare = pipeline_dir / "prepare_workbook_data.py"
    if prepare.exists():
        run_python(prepare, root)

    print("Week 6 unified run completed.")
    print("Main outputs:")
    print("  auto_output/subscription_auto.csv")
    print("  auto_output/transfer_auto.csv")
    print("  auto_output/equity_snapshot_auto.csv")
    print("  final/subscription_final.csv")
    print("  final/transfer_final.csv")
    print("  final/equity_snapshot_final.csv")
    print("  validation/cross_check.csv")
    print("  validation/auto_vs_gold.csv")
    print("  report/week6_report.md")


if __name__ == "__main__":
    main()
