"""Run every business-question SQL file and save its result to outputs/sql/<name>.csv.

Usage:
    python src/run_sql_analysis.py                 # run all files in sql/analysis
    python src/run_sql_analysis.py 08_category     # run files whose name contains the text
"""
import sys

from config import SQL_DIR, SQL_OUTPUT_DIR
from db import connect, run_sql_file


def main(name_filter: str = "") -> None:
    SQL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    con = connect()
    for path in sorted((SQL_DIR / "analysis").glob("*.sql")):
        if name_filter not in path.name:
            continue
        result = run_sql_file(con, path)
        result.to_csv(SQL_OUTPUT_DIR / f"{path.stem}.csv", index=False)
        print(f"  {path.name:<40}{len(result):>6} rows -> outputs/sql/{path.stem}.csv")
    con.close()


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "")
