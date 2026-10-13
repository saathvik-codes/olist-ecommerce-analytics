"""Test 1: do late deliveries get lower review scores?

Design
------
Population : delivered orders with a delivery date and a review (one review per order).
Groups     : on time vs late (delivered on a date after the promised date).
Outcome    : review score, an ordinal 1-5 scale that is heavily skewed towards 5.

Why these tests
---------------
* A t-test assumes an interval-scaled, roughly normal outcome. Review scores are ordinal,
  bounded and J-shaped, so the primary test is Mann-Whitney U (two-sided, tie-corrected
  normal approximation - valid here because both groups are large).
* A p-value on ~96k rows is almost always "significant", so the result is reported as
  effect sizes with 95% confidence intervals:
    - probability of superiority (AUC): chance a random on-time order is rated higher
      than a random late order, ties counted as half;
    - rank-biserial correlation = 2 * AUC - 1;
    - difference in mean score (bootstrap CI, since the scale is not normal);
    - difference and ratio in the share of low reviews (score <= 2), Newcombe / log CI.
* Chi-square test of independence on the 2 x 5 table as a distribution-level check.

Assumptions and how they are checked
------------------------------------
* Independence of observations: one review per order, but a customer can place several
  orders. 97% of customers have a single order; the test is repeated on each customer's
  first order only as a sensitivity check.
* Mann-Whitney makes no normality assumption. It tests stochastic dominance, not means.
* This is observational data: it shows association, not that lateness alone causes the
  drop (late orders are also slower in absolute terms and skew towards remote states).
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.proportion import confint_proportions_2indep

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from config import STATS_OUTPUT_DIR  # noqa: E402
from db import connect  # noqa: E402

SEED = 42
N_BOOTSTRAP = 5_000
SCORES = np.arange(1, 6)


def auc_from_counts(on_time: np.ndarray, late: np.ndarray) -> float:
    """P(on-time score > late score) + 0.5 * P(tie), from the two score histograms."""
    p_on, p_late = on_time / on_time.sum(), late / late.sum()
    late_below = np.concatenate([[0], np.cumsum(p_late)[:-1]])  # P(late < score)
    return float(np.sum(p_on * (late_below + 0.5 * p_late)))


def mean_from_counts(counts: np.ndarray) -> float:
    return float(np.sum(counts * SCORES) / counts.sum())


def bootstrap_ci(on_time: np.ndarray, late: np.ndarray) -> dict:
    """Percentile bootstrap. Resampling orders == multinomial draws of the score histogram."""
    rng = np.random.default_rng(SEED)
    on_draws = rng.multinomial(on_time.sum(), on_time / on_time.sum(), size=N_BOOTSTRAP)
    late_draws = rng.multinomial(late.sum(), late / late.sum(), size=N_BOOTSTRAP)
    mean_diff = (on_draws @ SCORES) / on_time.sum() - (late_draws @ SCORES) / late.sum()
    auc = np.array([auc_from_counts(a, b) for a, b in zip(on_draws, late_draws)])
    return {
        "mean_diff_ci95": np.percentile(mean_diff, [2.5, 97.5]).round(4).tolist(),
        "auc_ci95": np.percentile(auc, [2.5, 97.5]).round(4).tolist(),
    }


def analyse(df: pd.DataFrame) -> dict:
    on_time = df.loc[df.is_late == 0, "review_score"].to_numpy()
    late = df.loc[df.is_late == 1, "review_score"].to_numpy()
    on_counts = np.array([(on_time == s).sum() for s in SCORES])
    late_counts = np.array([(late == s).sum() for s in SCORES])

    u_stat, p_mwu = stats.mannwhitneyu(on_time, late, alternative="two-sided", method="asymptotic")
    auc = u_stat / (len(on_time) * len(late))
    chi2, p_chi2, dof, _ = stats.chi2_contingency(np.vstack([on_counts, late_counts]))
    cramers_v = float(np.sqrt(chi2 / (len(df) * 1)))  # min(rows, cols) - 1 = 1

    low_on, low_late = int((on_time <= 2).sum()), int((late <= 2).sum())
    rate_on, rate_late = low_on / len(on_time), low_late / len(late)
    diff_ci = confint_proportions_2indep(
        low_late, len(late), low_on, len(on_time), method="newcomb", compare="diff"
    )
    ratio_ci = confint_proportions_2indep(
        low_late, len(late), low_on, len(on_time), method="log", compare="ratio"
    )

    def describe(values: np.ndarray, counts: np.ndarray) -> dict:
        return {
            "n": int(len(values)),
            "mean": round(float(values.mean()), 3),
            "median": float(np.median(values)),
            "sd": round(float(values.std(ddof=1)), 3),
            "score_distribution_pct": (100 * counts / counts.sum()).round(2).tolist(),
            "low_review_rate_pct": round(100 * float((values <= 2).mean()), 2),
            "five_star_rate_pct": round(100 * float((values == 5).mean()), 2),
        }

    return {
        "on_time": describe(on_time, on_counts),
        "late": describe(late, late_counts),
        "mann_whitney_u": {
            "u_statistic": float(u_stat),
            "p_value": float(p_mwu),
            "auc_probability_of_superiority": round(float(auc), 4),
            "rank_biserial_correlation": round(float(2 * auc - 1), 4),
        },
        "mean_difference_on_time_minus_late": round(mean_from_counts(on_counts) - mean_from_counts(late_counts), 4),
        **bootstrap_ci(on_counts, late_counts),
        "chi_square": {
            "chi2": round(float(chi2), 1),
            "dof": int(dof),
            "p_value": float(p_chi2),
            "cramers_v": round(cramers_v, 4),
        },
        "low_review": {
            "rate_on_time_pct": round(100 * rate_on, 2),
            "rate_late_pct": round(100 * rate_late, 2),
            "risk_difference_pp": round(100 * (rate_late - rate_on), 2),
            "risk_difference_ci95_pp": [round(100 * x, 2) for x in diff_ci],
            "risk_ratio": round(rate_late / rate_on, 3),
            "risk_ratio_ci95": [round(x, 3) for x in ratio_ci],
        },
    }


def fmt_p(p: float) -> str:
    return "< 1e-300 (underflows to 0)" if p == 0 else f"{p:.3g}"


def main() -> None:
    con = connect(read_only=True)
    df = con.execute(
        """
        SELECT order_id, customer_order_seq, is_late, days_to_deliver, review_score
        FROM fact_orders
        WHERE is_delivered = 1 AND has_delivery_date = 1 AND review_score IS NOT NULL
        """
    ).df()
    con.close()

    main_result = analyse(df)
    first_order_only = analyse(df[df.customer_order_seq == 1])

    rho, p_rho = stats.spearmanr(df.days_to_deliver, df.review_score)
    z = np.arctanh(rho)
    se = 1.03 / np.sqrt(len(df) - 3)  # Bonett-Wright style approximation for Spearman
    rho_ci = np.tanh([z - 1.96 * se, z + 1.96 * se])

    results = {
        "test": "Late delivery vs review score",
        "n_orders": int(len(df)),
        "late_share_pct": round(100 * float(df.is_late.mean()), 2),
        "all_orders": main_result,
        "sensitivity_first_order_per_customer": {
            "n_orders": int((df.customer_order_seq == 1).sum()),
            "auc_probability_of_superiority": first_order_only["mann_whitney_u"]["auc_probability_of_superiority"],
            "mean_difference_on_time_minus_late": first_order_only["mean_difference_on_time_minus_late"],
            "mean_diff_ci95": first_order_only["mean_diff_ci95"],
            "risk_ratio_low_review": first_order_only["low_review"]["risk_ratio"],
        },
        "spearman_days_to_deliver_vs_review": {
            "rho": round(float(rho), 4),
            "ci95": [round(float(x), 4) for x in rho_ci],
            "p_value": float(p_rho),
        },
        "bootstrap": {"resamples": N_BOOTSTRAP, "seed": SEED},
    }

    STATS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (STATS_OUTPUT_DIR / "late_delivery_vs_reviews.json").write_text(json.dumps(results, indent=2))

    r, low, mwu = main_result, main_result["low_review"], main_result["mann_whitney_u"]
    sens = results["sensitivity_first_order_per_customer"]
    sp = results["spearman_days_to_deliver_vs_review"]
    md = f"""# Test 1 - Do late deliveries get lower review scores?

Generated by `analysis/01_late_delivery_vs_reviews.py`. Population: {len(df):,} delivered,
reviewed orders; {results['late_share_pct']}% of them arrived after the promised date.

| Group | Orders | Mean score | Median | SD | Low reviews (<=2) | 5-star |
|---|---:|---:|---:|---:|---:|---:|
| On time | {r['on_time']['n']:,} | {r['on_time']['mean']} | {r['on_time']['median']:.0f} | {r['on_time']['sd']} | {r['on_time']['low_review_rate_pct']}% | {r['on_time']['five_star_rate_pct']}% |
| Late | {r['late']['n']:,} | {r['late']['mean']} | {r['late']['median']:.0f} | {r['late']['sd']} | {r['late']['low_review_rate_pct']}% | {r['late']['five_star_rate_pct']}% |

## Results

| Measure | Estimate | 95% CI |
|---|---:|---:|
| Difference in mean score (on time - late) | {r['mean_difference_on_time_minus_late']} | {r['mean_diff_ci95'][0]} to {r['mean_diff_ci95'][1]} (bootstrap) |
| Probability a random on-time order outscores a random late one (AUC) | {mwu['auc_probability_of_superiority']} | {r['auc_ci95'][0]} to {r['auc_ci95'][1]} (bootstrap) |
| Rank-biserial correlation | {mwu['rank_biserial_correlation']} | |
| Low-review rate: late vs on time | {low['rate_late_pct']}% vs {low['rate_on_time_pct']}% | |
| Risk difference (percentage points) | {low['risk_difference_pp']} | {low['risk_difference_ci95_pp'][0]} to {low['risk_difference_ci95_pp'][1]} (Newcombe) |
| Risk ratio | {low['risk_ratio']} | {low['risk_ratio_ci95'][0]} to {low['risk_ratio_ci95'][1]} |
| Cramer's V (2 x 5 table) | {r['chi_square']['cramers_v']} | |
| Spearman rho, days to deliver vs score | {sp['rho']} | {sp['ci95'][0]} to {sp['ci95'][1]} |

* Mann-Whitney U = {mwu['u_statistic']:,.0f}, two-sided p {fmt_p(mwu['p_value'])}.
* Chi-square = {r['chi_square']['chi2']:,} on {r['chi_square']['dof']} df, p {fmt_p(r['chi_square']['p_value'])}.

## Reading it

Late orders are rated about {r['mean_difference_on_time_minus_late']:.2f} points lower on a 5-point scale, and are
{low['risk_ratio']:.1f}x as likely to receive a 1-2 star review. The rank-biserial correlation of
{mwu['rank_biserial_correlation']} is a large effect by the usual conventions. With n this large the p-value carries
no information beyond "not zero"; the effect sizes are the result.

Across all orders the monotonic link between delivery days and score is weaker
(Spearman rho {sp['rho']}): most orders arrive in a normal window where a day more or less
barely matters. The damage is concentrated in the orders that break the promise.

## Assumption checks

* Scale: ordinal and skewed (median 5 on time), so a rank test and bootstrap CIs were used
  instead of a t-test.
* Independence: repeating the test on each customer's first order only (n = {sens['n_orders']:,})
  gives AUC {sens['auc_probability_of_superiority']}, mean difference {sens['mean_difference_on_time_minus_late']}
  (CI {sens['mean_diff_ci95'][0]} to {sens['mean_diff_ci95'][1]}) and risk ratio {sens['risk_ratio_low_review']} - effectively unchanged.
* Causality: observational. Late orders are also slower in absolute terms and skew towards
  remote states; test 2 separates those factors.
* Missing reviews: orders without a review are excluded; if unhappy customers review more
  (or less) often, the absolute rates shift, but both groups are affected.
"""
    (STATS_OUTPUT_DIR / "late_delivery_vs_reviews.md").write_text(md, encoding="utf-8")
    print(
        f"  mean diff {r['mean_difference_on_time_minus_late']} "
        f"CI {r['mean_diff_ci95']}, AUC {mwu['auc_probability_of_superiority']}, "
        f"risk ratio {low['risk_ratio']}"
    )


if __name__ == "__main__":
    main()
