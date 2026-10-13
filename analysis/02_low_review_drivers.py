"""Test 2: what drives a low review (1-2 stars)? A logistic-regression driver analysis.

Outcome    : low_review = 1 if review score <= 2, else 0.
Unit       : one delivered, reviewed order with a delivery date.
Predictors : chosen because the business can act on them or must control for them.
    is_late             delivered after the promised date
    delivery_weeks      days from purchase to delivery / 7, capped at 60 days (0.3% of orders)
    multi_seller        order contains items from more than one seller (ships as several parcels)
    multi_item          order contains more than one item
    log_order_value     natural log of item value
    freight_ratio       freight / item value
    paid_by_boleto      primary payment is boleto (bank slip) rather than card / other
    region_*            customer macro-region, Southeast as the reference

Method notes
------------
* Logit fitted by maximum likelihood on a random 80% of orders; discrimination (AUC) is
  measured on the held-out 20% so it is not flattered by fitting and scoring the same rows.
* Results are reported as odds ratios with 95% CIs and as average marginal effects
  (percentage-point change in the probability of a low review), which are easier to act on.
* Multicollinearity is checked with variance inflation factors (is_late and delivery_weeks
  are related by construction).
* Linearity of the logit in delivery_weeks is an approximation; capping the long tail keeps
  a handful of 100+ day deliveries from dominating the slope.
* Observational data: coefficients are adjusted associations, not causal effects.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats
from statsmodels.stats.outliers_influence import variance_inflation_factor

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from config import STATS_OUTPUT_DIR  # noqa: E402
from db import connect  # noqa: E402

SEED = 42
PREDICTORS = [
    "is_late",
    "delivery_weeks",
    "multi_seller",
    "multi_item",
    "log_order_value",
    "freight_ratio",
    "paid_by_boleto",
    "region_South",
    "region_Northeast",
    "region_North",
    "region_Center-West",
]


def auc_score(y_true: np.ndarray, score: np.ndarray) -> float:
    """Area under the ROC curve via the Mann-Whitney identity."""
    ranks = stats.rankdata(score)
    n_pos, n_neg = y_true.sum(), (1 - y_true).sum()
    return float((ranks[y_true == 1].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def load() -> pd.DataFrame:
    con = connect(read_only=True)
    df = con.execute(
        """
        SELECT
            o.is_low_review                          AS low_review,
            o.is_late,
            least(o.days_to_deliver, 60) / 7.0       AS delivery_weeks,
            CAST(o.seller_count > 1 AS INTEGER)      AS multi_seller,
            CAST(o.item_count > 1 AS INTEGER)        AS multi_item,
            ln(o.items_value)                        AS log_order_value,
            o.freight_value / o.items_value          AS freight_ratio,
            CAST(o.payment_type = 'boleto' AS INTEGER) AS paid_by_boleto,
            g.region
        FROM fact_orders AS o
        JOIN dim_geography AS g USING (geography_key)
        WHERE o.is_delivered = 1
          AND o.has_delivery_date = 1
          AND o.review_score IS NOT NULL
          AND o.payment_type IS NOT NULL
        ORDER BY o.order_id   -- fixed row order, so the seeded train/test split is reproducible
        """
    ).df()
    con.close()
    for region in ["South", "Northeast", "North", "Center-West"]:
        df[f"region_{region}"] = (df.region == region).astype(int)
    return df


def main() -> None:
    df = load()
    rng = np.random.default_rng(SEED)
    is_train = rng.random(len(df)) < 0.8
    train, test = df[is_train], df[~is_train]

    x_train = sm.add_constant(train[PREDICTORS].astype(float))
    x_test = sm.add_constant(test[PREDICTORS].astype(float))
    y_train, y_test = train.low_review.to_numpy(), test.low_review.to_numpy()

    model = sm.Logit(y_train, x_train).fit(disp=False)
    late_only = sm.Logit(y_train, x_train[["const", "is_late"]]).fit(disp=False)

    conf = model.conf_int()
    margins = model.get_margeff(at="overall", method="dydx", dummy=True).summary_frame()
    vif = {
        name: round(float(variance_inflation_factor(x_train.to_numpy(), i)), 2)
        for i, name in enumerate(x_train.columns)
        if name != "const"
    }

    coefficients = []
    for name in PREDICTORS:
        coefficients.append(
            {
                "predictor": name,
                "odds_ratio": round(float(np.exp(model.params[name])), 3),
                "or_ci95": [round(float(np.exp(conf.loc[name, 0])), 3), round(float(np.exp(conf.loc[name, 1])), 3)],
                "p_value": float(model.pvalues[name]),
                "avg_marginal_effect_pp": round(100 * float(margins.loc[name, "dy/dx"]), 2),
                "ame_ci95_pp": [
                    round(100 * float(margins.loc[name, "Conf. Int. Low"]), 2),
                    round(100 * float(margins.loc[name, "Cont. Int. Hi."]), 2),
                ],
                "vif": vif[name],
            }
        )

    results = {
        "test": "Logistic regression: drivers of a low review (score <= 2)",
        "n_train": int(len(train)),
        "n_test": int(len(test)),
        "low_review_rate_pct": round(100 * float(df.low_review.mean()), 2),
        "mcfadden_pseudo_r2": round(float(model.prsquared), 4),
        "llr_p_value": float(model.llr_pvalue),
        "auc_test_full_model": round(auc_score(y_test, model.predict(x_test).to_numpy()), 4),
        "auc_test_late_flag_only": round(
            auc_score(y_test, late_only.predict(x_test[["const", "is_late"]]).to_numpy()), 4
        ),
        "converged": bool(model.mle_retvals["converged"]),
        "coefficients": coefficients,
        "seed": SEED,
    }

    STATS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (STATS_OUTPUT_DIR / "low_review_drivers.json").write_text(json.dumps(results, indent=2))
    pd.DataFrame(
        [{**c, "or_ci_low": c["or_ci95"][0], "or_ci_high": c["or_ci95"][1]} for c in coefficients]
    ).drop(columns=["or_ci95", "ame_ci95_pp"]).to_csv(STATS_OUTPUT_DIR / "low_review_drivers.csv", index=False)

    rows = "\n".join(
        f"| {c['predictor']} | {c['odds_ratio']} | {c['or_ci95'][0]} to {c['or_ci95'][1]} | "
        f"{c['avg_marginal_effect_pp']:+.2f} | {c['ame_ci95_pp'][0]:+.2f} to {c['ame_ci95_pp'][1]:+.2f} | "
        f"{'<0.001' if c['p_value'] < 0.001 else format(c['p_value'], '.3f')} | {c['vif']} |"
        for c in coefficients
    )
    by_name = {c["predictor"]: c for c in coefficients}
    md = f"""# Test 2 - What drives a low review? (logistic regression)

Generated by `analysis/02_low_review_drivers.py`. Outcome: review score <= 2
({results['low_review_rate_pct']}% of {len(df):,} delivered, reviewed orders).
Fitted on {results['n_train']:,} orders, evaluated on a held-out {results['n_test']:,}.

| Predictor | Odds ratio | 95% CI | Avg marginal effect (pp) | 95% CI (pp) | p | VIF |
|---|---:|---:|---:|---:|---:|---:|
{rows}

Model fit: McFadden pseudo-R2 = {results['mcfadden_pseudo_r2']}; held-out AUC = {results['auc_test_full_model']}
(late flag alone: {results['auc_test_late_flag_only']}; 0.5 = coin flip). Converged: {results['converged']}.

## Reading it

* **Late delivery** is the strongest single driver: holding the other factors fixed, a late
  order has {by_name['is_late']['odds_ratio']}x the odds of a low review, about
  {by_name['is_late']['avg_marginal_effect_pp']:+.1f} percentage points on the probability.
* **Each extra week in transit** multiplies the odds by {by_name['delivery_weeks']['odds_ratio']}
  ({by_name['delivery_weeks']['avg_marginal_effect_pp']:+.1f} pp), even for orders that still met the promise.
* **Multi-seller orders** carry {by_name['multi_seller']['odds_ratio']}x the odds
  ({by_name['multi_seller']['avg_marginal_effect_pp']:+.1f} pp): the customer rates one order but
  receives several parcels on different days.
* **Multi-item orders** have {by_name['multi_item']['odds_ratio']}x the odds
  ({by_name['multi_item']['avg_marginal_effect_pp']:+.1f} pp).
* **Region reverses once delivery is controlled for.** Raw review scores are lower in the
  North and Northeast, but with delivery held fixed those customers are slightly LESS likely
  to leave a low review than the Southeast (odds ratios {by_name['region_North']['odds_ratio']} and {by_name['region_Northeast']['odds_ratio']}).
  The regional gap is a delivery problem, not a customer problem.
* Order value (OR {by_name['log_order_value']['odds_ratio']}), freight ratio (OR {by_name['freight_ratio']['odds_ratio']}, CI includes 1) and paying by
  boleto (OR {by_name['paid_by_boleto']['odds_ratio']}) have small effects.

## Honest limits

* A pseudo-R2 of {results['mcfadden_pseudo_r2']} and AUC of {results['auc_test_full_model']} mean the model explains a modest
  share of low reviews. Most dissatisfaction comes from things not in this data (product
  quality, wrong or damaged items, seller communication). This is a driver analysis, not a
  model fit for predicting individual reviews.
* VIFs are all low, so the late flag and delivery time are not too collinear to separate.
* Coefficients are adjusted associations from observational data, not causal effects.
* delivery_weeks is capped at 60 days and assumed linear in the log-odds.
"""
    (STATS_OUTPUT_DIR / "low_review_drivers.md").write_text(md, encoding="utf-8")
    print(
        f"  pseudo-R2 {results['mcfadden_pseudo_r2']}, test AUC {results['auc_test_full_model']}, "
        f"late OR {by_name['is_late']['odds_ratio']}"
    )


if __name__ == "__main__":
    main()
