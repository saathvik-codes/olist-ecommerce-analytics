"""Small DuckDB helpers: connect to the warehouse and run .sql files."""
import os
from pathlib import Path

import duckdb
import pandas as pd

from config import ROOT, WAREHOUSE


def connect(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """Open the warehouse. SQL files use paths relative to the project root."""
    os.chdir(ROOT)
    WAREHOUSE.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(WAREHOUSE), read_only=read_only)


def run_sql_file(con: duckdb.DuckDBPyConnection, path: Path) -> pd.DataFrame | None:
    """Execute every statement in a file; return the last statement's result set.

    A file may build helper tables first (CREATE OR REPLACE TABLE ...) and must
    end with the SELECT that answers its business question.
    """
    result = con.execute(Path(path).read_text(encoding="utf-8"))
    if result.description is None:
        return None
    return result.df()
