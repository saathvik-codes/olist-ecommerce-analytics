"""Sanity checks on the cohort-retention matrix and the RFM segmentation."""
import pandas as pd
import pytest

from config import SQL_OUTPUT_DIR
from conftest import scalar

LAST_COMPLETE_MONTH = pd.Period("2018-08", freq="M")


@pytest.fixture(scope="module")
def cohorts(con) -> pd.DataFrame:
    return con.execute("SELECT * FROM mart_cohort_retention").df()


@pytest.fixture(scope="module")
def matrix() -> pd.DataFrame:
    return pd.read_csv(SQL_OUTPUT_DIR / "02_cohort_retention.csv")


def test_month_zero_is_the_whole_cohort(cohorts):
    month_zero = cohorts[cohorts.month_offset == 0]
    assert len(month_zero) == cohorts.cohort_month.nunique() == 20
    assert (month_zero.active_customers == month_zero.cohort_size).all()
    assert (month_zero.retention_pct == 100).all()


def test_retention_is_a_valid_share(cohorts):
    assert cohorts.month_offset.min() == 0
    assert (cohorts.active_customers <= cohorts.cohort_size).all()
    assert cohorts.retention_pct.between(0, 100).all()
    assert not cohorts.duplicated(["cohort_month", "month_offset"]).any()


def test_cohort_sizes_match_new_customers_per_month(matrix):
    monthly = pd.read_csv(SQL_OUTPUT_DIR / "01_monthly_revenue_growth.csv")
    new_customers = monthly[monthly.is_complete_month == 1].set_index("year_month").new_customers
    sizes = matrix.set_index("cohort_month").cohort_size
    assert sizes.to_dict() == new_customers.to_dict()


def test_every_customer_belongs_to_exactly_one_cohort(con, matrix):
    in_window = scalar(
        con,
        "SELECT count(*) FROM dim_customer WHERE cohort_month BETWEEN '2017-01' AND '2018-08'",
    )
    assert matrix.cohort_size.sum() == in_window


def test_unobserved_months_are_blank_not_zero(matrix):
    for row in matrix.itertuples():
        cohort = pd.Period(row.cohort_month, freq="M")
        for offset in range(1, 13):
            value = getattr(row, f"m{offset}")
            if cohort + offset > LAST_COMPLETE_MONTH:
                assert pd.isna(value), f"{row.cohort_month} m{offset} should be blank"
            else:
                assert value >= 0, f"{row.cohort_month} m{offset} should be observed"


def test_matrix_agrees_with_long_table(cohorts, matrix):
    lookup = cohorts.set_index(["cohort_month", "month_offset"]).active_customers
    for row in matrix.itertuples():
        for offset in range(1, 13):
            value = getattr(row, f"m{offset}")
            if pd.notna(value):
                assert value == lookup.get((row.cohort_month, offset), 0)


def test_rfm_assigns_every_customer_one_segment(con, kpi):
    customers, distinct, unscored = con.execute(
        """
        SELECT count(*), count(DISTINCT customer_key),
               count(*) FILTER (WHERE rfm_segment IS NULL
                                   OR r_score NOT BETWEEN 1 AND 5
                                   OR m_score NOT BETWEEN 1 AND 5
                                   OR f_score NOT IN (1, 3, 5))
        FROM mart_customer_rfm
        """
    ).fetchone()
    assert customers == distinct == kpi.customers
    assert unscored == 0
    assert scalar(con, "SELECT sum(monetary) FROM mart_customer_rfm") == pytest.approx(kpi.total_revenue, abs=0.05)
