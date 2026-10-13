"""Build the DuckDB warehouse: raw -> staging -> star schema."""
from config import SQL_DIR, STAR_TABLES
from db import connect, run_sql_file


def main() -> None:
    con = connect()
    for path in sorted((SQL_DIR / "model").glob("*.sql")):
        print(f"  running {path.name}")
        run_sql_file(con, path)
    for table in STAR_TABLES + ["fact_payments"]:
        rows = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        print(f"  {table:<18}{rows:>10,} rows")
    con.close()


if __name__ == "__main__":
    main()
