"""Reproduce the whole project with one command:  python run_all.py

Steps: download + verify data -> build the DuckDB star schema -> data-quality report ->
SQL analyses -> statistics -> Power BI export + DAX expected values -> Excel report ->
charts -> tests. Stops at the first failing step.
"""
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent

STEPS = [
    ("Download and verify the Olist dataset", ["src/download_data.py"]),
    ("Build the DuckDB warehouse (staging + star schema)", ["src/build_warehouse.py"]),
    ("Data-quality report", ["src/data_quality.py"]),
    ("SQL business analyses", ["src/run_sql_analysis.py"]),
    ("Statistics 1: late delivery vs review score", ["analysis/01_late_delivery_vs_reviews.py"]),
    ("Statistics 2: drivers of low reviews", ["analysis/02_low_review_drivers.py"]),
    ("Export star schema for Power BI", ["src/export_powerbi.py"]),
    ("Expected values for the DAX measures", ["src/validate_dax.py"]),
    ("Excel executive report", ["src/build_excel.py"]),
    ("Charts", ["src/make_charts.py"]),
    ("Tests", ["-m", "pytest", "tests", "-q"]),
]


def main() -> int:
    started = time.time()
    for number, (label, args) in enumerate(STEPS, start=1):
        print(f"\n[{number}/{len(STEPS)}] {label}", flush=True)
        step_started = time.time()
        result = subprocess.run([sys.executable, *args], cwd=ROOT)
        if result.returncode != 0:
            print(f"\nFAILED at step {number}: {label}")
            return result.returncode
        print(f"  done in {time.time() - step_started:.1f}s", flush=True)
    print(f"\nAll {len(STEPS)} steps finished in {time.time() - started:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
