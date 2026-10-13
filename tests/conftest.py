"""Shared fixtures. Tests run against the artefacts produced by `python run_all.py`."""
import sys
from pathlib import Path

import duckdb
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from config import EXCEL_REPORT, SQL_OUTPUT_DIR, WAREHOUSE  # noqa: E402


@pytest.fixture(scope="session")
def con():
    connection = duckdb.connect(str(WAREHOUSE), read_only=True)
    yield connection
    connection.close()


@pytest.fixture(scope="session")
def kpi() -> pd.Series:
    return pd.read_csv(SQL_OUTPUT_DIR / "00_headline_kpis.csv").set_index("metric").value


@pytest.fixture(scope="session")
def workbook():
    from openpyxl import load_workbook

    return load_workbook(EXCEL_REPORT)  # formulas kept as text, not evaluated


def scalar(con, sql: str):
    return con.execute(sql).fetchone()[0]
