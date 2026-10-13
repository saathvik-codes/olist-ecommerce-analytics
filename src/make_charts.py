"""Render the charts used in INSIGHTS.md and the README (outputs/charts/*.png).

Every chart reads the CSV / JSON written by the SQL and statistics steps, so a chart can
never disagree with the numbers in the tables. One measure per axis; colour encodes
identity (blue / orange) or magnitude (single-hue ramp), never decoration.
"""
import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.ticker import FuncFormatter, PercentFormatter  # noqa: E402

from config import CHART_DIR, SQL_OUTPUT_DIR, STATS_OUTPUT_DIR  # noqa: E402

SURFACE, INK, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
BLUE, ORANGE = "#2a78d6", "#eb6834"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "font.family": "DejaVu Sans", "font.size": 10, "text.color": INK,
    "axes.edgecolor": GRID, "axes.labelcolor": MUTED, "axes.titlesize": 13, "axes.titleweight": "bold",
    "axes.titlelocation": "left", "axes.spines.top": False, "axes.spines.right": False,
    "axes.spines.left": False, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.axisbelow": True, "xtick.color": MUTED, "ytick.color": MUTED,
    "xtick.major.size": 0, "ytick.major.size": 0, "legend.frameon": False,
})


def read(name: str) -> pd.DataFrame:
    return pd.read_csv(SQL_OUTPUT_DIR / f"{name}.csv")


def save(fig, name: str, subtitle: str | None = None) -> None:
    if subtitle:
        fig.text(0.012, 0.012, subtitle, fontsize=8, color=MUTED, ha="left", va="bottom")
    fig.savefig(CHART_DIR / f"{name}.png", dpi=150, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)


def thousands(value, _pos=None) -> str:
    return f"{value / 1000:,.0f}k"


def monthly_revenue() -> None:
    df = read("01_monthly_revenue_growth").query("is_complete_month == 1")
    months = pd.to_datetime(df.year_month)
    fig, ax = plt.subplots(figsize=(10, 4.4))
    ax.plot(months, df.revenue, color=BLUE, linewidth=2)
    ax.grid(axis="x", visible=False)
    ax.yaxis.set_major_formatter(FuncFormatter(thousands))
    ax.set_ylim(0, df.revenue.max() * 1.15)
    ax.set_ylabel("Revenue (R$)")
    growth = df.revenue.iloc[-1] / df.revenue.iloc[0]
    ax.set_title(f"Monthly revenue grew {growth:.1f}x from Jan-2017 to Aug-2018, flattening through 2018")
    peak = df.loc[df.revenue.idxmax()]
    for row, offset in [(peak, (0, 10)), (df.iloc[0], (0, 10)), (df.iloc[-1], (0, 10))]:
        ax.annotate(f"R$ {row.revenue / 1000:,.0f}k\n{pd.to_datetime(row.year_month):%b %Y}",
                    (pd.to_datetime(row.year_month), row.revenue), textcoords="offset points",
                    xytext=offset, ha="center", fontsize=9, color=INK)
        ax.scatter([pd.to_datetime(row.year_month)], [row.revenue], color=BLUE, s=36, zorder=3,
                   edgecolor=SURFACE, linewidth=2)
    save(fig, "01_monthly_revenue", "Delivered orders, item revenue, complete months only (Jan-2017 to Aug-2018).")


def delivery_vs_review() -> None:
    df = read("05_delivery_time_vs_review")
    labels = df.delivery_band.str.split(". ", n=1).str[1]
    fig, ax = plt.subplots(figsize=(8.5, 4.4))
    bars = ax.bar(labels, df.avg_review, color=BLUE, width=0.62)
    ax.bar_label(bars, labels=[f"{v:.2f}" for v in df.avg_review], padding=3, color=INK, fontsize=10)
    ax.set_ylim(0, 5.3)
    ax.grid(axis="x", visible=False)
    ax.set_ylabel("Average review score (1-5)")
    ax.set_xlabel("Days from purchase to delivery")
    ax.set_title("Satisfaction holds for three weeks, then collapses")
    save(fig, "02_delivery_time_vs_review",
         f"n = {df.orders.sum():,} delivered and reviewed orders. {df.pct_of_orders.iloc[-2:].sum():.1f}% of orders take 22+ days.")


def late_vs_on_time() -> None:
    stats = json.loads((STATS_OUTPUT_DIR / "late_delivery_vs_reviews.json").read_text())["all_orders"]
    scores = np.arange(1, 6)
    fig, ax = plt.subplots(figsize=(8.5, 4.4))
    width = 0.38
    on = ax.bar(scores - width / 2 - 0.01, stats["on_time"]["score_distribution_pct"], width, color=BLUE,
                label=f"On time (n = {stats['on_time']['n']:,})")
    late = ax.bar(scores + width / 2 + 0.01, stats["late"]["score_distribution_pct"], width, color=ORANGE,
                  label=f"Late (n = {stats['late']['n']:,})")
    ax.bar_label(on, fmt="%.0f%%", padding=2, fontsize=9, color=INK)
    ax.bar_label(late, fmt="%.0f%%", padding=2, fontsize=9, color=INK)
    ax.set_xticks(scores, [f"{s} star" + ("s" if s > 1 else "") for s in scores])
    ax.yaxis.set_major_formatter(PercentFormatter(decimals=0))
    ax.set_ylim(0, 72)
    ax.grid(axis="x", visible=False)
    ax.set_ylabel("Share of orders in the group")
    ax.set_title("Late orders flip the review distribution from 5 stars to 1 star")
    ax.legend(loc="upper center")
    save(fig, "03_review_distribution_late_vs_on_time",
         f"Mean score {stats['on_time']['mean']} on time vs {stats['late']['mean']} late. "
         "Late = delivered after the promised date.")


def late_by_state() -> None:
    df = read("06_late_delivery_by_state").sort_values("late_rate_pct")
    national = 100 * df.late_orders.sum() / df.delivered_orders.sum()
    fig, ax = plt.subplots(figsize=(8.5, 7.2))
    bars = ax.barh(df.state + "  " + df.state_name, df.late_rate_pct, color=BLUE, height=0.68)
    ax.bar_label(bars, labels=[f"{v:.1f}%" for v in df.late_rate_pct], padding=3, fontsize=8.5, color=INK)
    ax.axvline(national, color=MUTED, linewidth=1.2, linestyle=(0, (4, 3)))
    ax.text(national + 0.2, 0.3, f"National {national:.1f}%", color=MUTED, fontsize=9, va="bottom")
    ax.xaxis.set_major_formatter(PercentFormatter(decimals=0))
    ax.set_xlim(0, df.late_rate_pct.max() * 1.12)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Share of delivered orders arriving after the promised date")
    ax.set_title("Late deliveries: the Northeast and Rio de Janeiro miss the promise most often")
    rj = df[df.state == "RJ"].iloc[0]
    save(fig, "04_late_rate_by_state",
         f"Rio de Janeiro alone accounts for {rj.pct_of_all_late_orders:.1f}% of all late orders "
         f"({rj.pct_of_all_orders:.1f}% of orders).")


def category_pareto() -> None:
    df = read("08_category_pareto")
    top = df.head(20).iloc[::-1]
    class_a = int((df.abc_class == "A").sum())
    fig, (left, right) = plt.subplots(1, 2, figsize=(13, 6), gridspec_kw={"width_ratios": [1.15, 1]})
    bars = left.barh(top.category.str.replace("_", " "), top.revenue, color=BLUE, height=0.68)
    left.bar_label(bars, labels=[f"{v:.1f}%" for v in top.revenue_share_pct], padding=3, fontsize=8.5, color=INK)
    left.xaxis.set_major_formatter(FuncFormatter(thousands))
    left.set_xlim(0, top.revenue.max() * 1.12)
    left.grid(axis="y", visible=False)
    left.set_xlabel("Revenue (R$), label = share of total")
    left.set_title("Top 20 categories by revenue")

    right.plot(df.revenue_rank, df.cumulative_share_pct, color=BLUE, linewidth=2)
    right.axhline(80, color=MUTED, linewidth=1.2, linestyle=(0, (4, 3)))
    right.scatter([class_a], [df.cumulative_share_pct.iloc[class_a - 1]], color=BLUE, s=42, zorder=3,
                  edgecolor=SURFACE, linewidth=2)
    right.annotate(f"{class_a} of {len(df)} categories\nreach {df.cumulative_share_pct.iloc[class_a - 1]:.0f}% of revenue",
                   (class_a, df.cumulative_share_pct.iloc[class_a - 1]), textcoords="offset points",
                   xytext=(14, -30), fontsize=9.5, color=INK)
    right.yaxis.set_major_formatter(PercentFormatter(decimals=0))
    right.set_ylim(0, 104)
    right.set_xlim(0, len(df) + 1)
    right.set_xlabel("Category rank by revenue")
    right.set_ylabel("Cumulative share of revenue")
    right.set_title("Cumulative share (Pareto curve)")
    save(fig, "05_category_pareto", "Delivered orders. 'unknown' = products with no category in the source data.")


def cohort_heatmap() -> None:
    df = read("02_cohort_retention")
    offsets = [f"m{n}" for n in range(1, 13)]
    pct = df[offsets].div(df.cohort_size, axis=0) * 100
    fig, ax = plt.subplots(figsize=(11, 6.6))
    image = ax.imshow(np.ma.masked_invalid(pct.to_numpy()), cmap="Blues", aspect="auto", vmin=0,
                      vmax=float(np.nanmax(pct.to_numpy())))
    ax.set_xticks(range(12), [f"+{n}" for n in range(1, 13)])
    ax.set_yticks(range(len(df)), [f"{m}  (n={s:,})" for m, s in zip(df.cohort_month, df.cohort_size)])
    ax.grid(False)
    threshold = np.nanmax(pct.to_numpy()) * 0.55
    for (row, col), value in np.ndenumerate(pct.to_numpy()):
        if not np.isnan(value):
            ax.text(col, row, f"{value:.2f}", ha="center", va="center", fontsize=7.5,
                    color="white" if value > threshold else INK)
    ax.set_xlabel("Months since first order")
    ax.set_title("Cohort retention (% of cohort ordering again): well under 1% in any later month")
    colorbar = fig.colorbar(image, ax=ax, fraction=0.025, pad=0.02)
    colorbar.outline.set_visible(False)
    colorbar.set_label("% of cohort", color=MUTED)
    save(fig, "06_cohort_retention_heatmap",
         "Cohort = month of first delivered order. Blank cells are months not yet observed (data ends Aug-2018).")


def rfm_segments() -> None:
    df = read("03_rfm_segmentation").iloc[::-1]
    y = np.arange(len(df))
    fig, ax = plt.subplots(figsize=(9.5, 5.6))
    height = 0.38
    customers = ax.barh(y + height / 2 + 0.01, df.pct_of_customers, height, color=BLUE, label="% of customers")
    revenue = ax.barh(y - height / 2 - 0.01, df.pct_of_revenue, height, color=ORANGE, label="% of revenue")
    ax.bar_label(customers, fmt="%.1f%%", padding=3, fontsize=8.5, color=INK)
    ax.bar_label(revenue, fmt="%.1f%%", padding=3, fontsize=8.5, color=INK)
    ax.set_yticks(y, df.rfm_segment.str.split(". ", n=1).str[1])
    ax.xaxis.set_major_formatter(PercentFormatter(decimals=0))
    ax.set_xlim(0, max(df.pct_of_customers.max(), df.pct_of_revenue.max()) * 1.14)
    ax.grid(axis="y", visible=False)
    high = df[df.rfm_segment.str.contains("high-value")]
    ax.set_title(f"High-value one-time buyers are {high.pct_of_customers.sum():.0f}% of customers "
                 f"but {high.pct_of_revenue.sum():.0f}% of revenue")
    ax.legend(loc="lower right")
    save(fig, "07_rfm_segments",
         f"High-value segments (new, cooling, lost): {high.pct_of_customers.sum():.1f}% of customers, "
         f"{high.pct_of_revenue.sum():.1f}% of revenue. Repeat-buyer segments total under 3% of customers.")


def seller_concentration() -> None:
    df = read("11_seller_concentration")
    labels = df.seller_tier.str.split(". ", n=1).str[1]
    seller_share = 100 * df.sellers / df.sellers.sum()
    x = np.arange(len(df))
    fig, ax = plt.subplots(figsize=(9.5, 4.6))
    width = 0.38
    a = ax.bar(x - width / 2 - 0.01, seller_share, width, color=BLUE, label="% of sellers")
    b = ax.bar(x + width / 2 + 0.01, df.pct_of_revenue, width, color=ORANGE, label="% of revenue")
    ax.bar_label(a, fmt="%.0f%%", padding=2, fontsize=9, color=INK)
    ax.bar_label(b, fmt="%.0f%%", padding=2, fontsize=9, color=INK)
    ax.set_xticks(x, [label.replace(" (", "\n(") for label in labels], fontsize=9)
    ax.yaxis.set_major_formatter(PercentFormatter(decimals=0))
    ax.set_ylim(0, 58)
    ax.grid(axis="x", visible=False)
    ax.set_title(f"The top 5% of sellers bring in {df.cumulative_pct_of_revenue.iloc[1]:.0f}% of revenue")
    ax.legend(loc="upper right")
    save(fig, "08_seller_concentration",
         f"{df.sellers.sum():,} sellers with delivered sales. HHI = {df.marketplace_hhi.iloc[0]:.0f} "
         "(no single seller dominates; the largest holds under 2%).")


def low_review_drivers() -> None:
    results = json.loads((STATS_OUTPUT_DIR / "low_review_drivers.json").read_text())
    names = {
        "is_late": "Delivered late", "multi_seller": "Items from 2+ sellers", "multi_item": "2+ items in order",
        "delivery_weeks": "Each extra week in transit", "freight_ratio": "Freight / item value (+1.0)",
        "log_order_value": "Order value (per log unit)", "paid_by_boleto": "Paid by boleto",
        "region_Center-West": "Center-West (vs Southeast)", "region_South": "South (vs Southeast)",
        "region_Northeast": "Northeast (vs Southeast)", "region_North": "North (vs Southeast)",
    }
    coefs = sorted(results["coefficients"], key=lambda c: c["odds_ratio"])
    y = np.arange(len(coefs))
    ratios = np.array([c["odds_ratio"] for c in coefs])
    low = np.array([c["or_ci95"][0] for c in coefs])
    high = np.array([c["or_ci95"][1] for c in coefs])
    fig, ax = plt.subplots(figsize=(9.5, 5.2))
    ax.errorbar(ratios, y, xerr=[ratios - low, high - ratios], fmt="o", color=BLUE, ecolor=BLUE,
                elinewidth=2, markersize=7, markeredgecolor=SURFACE, markeredgewidth=1.5)
    ax.axvline(1, color=MUTED, linewidth=1.2, linestyle=(0, (4, 3)))
    ax.set_xscale("log")
    ax.set_xticks([0.5, 1, 2, 4, 8], ["0.5x", "1x", "2x", "4x", "8x"])
    ax.minorticks_off()
    ax.set_xlim(0.45, 11)
    for value, position in zip(ratios, y):
        ax.text(10.4, position, f"{value:.2f}x", va="center", ha="right", fontsize=9, color=INK)
    ax.set_yticks(y, [names[c["predictor"]] for c in coefs])
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Odds ratio for a 1-2 star review (log scale), with 95% confidence interval")
    ax.set_title("What drives a low review: lateness first, then split shipments")
    save(fig, "09_low_review_drivers",
         f"Logistic regression, n = {results['n_train']:,} orders; held-out AUC {results['auc_test_full_model']:.2f}, "
         f"pseudo-R2 {results['mcfadden_pseudo_r2']:.2f}. Adjusted associations, not causal effects.")


def installments() -> None:
    df = read("10_installments_vs_order_value")
    labels = df.installment_band.str.split(". ", n=1).str[1]
    fig, ax = plt.subplots(figsize=(8.5, 4.4))
    bars = ax.bar(labels, df.avg_order_value, color=BLUE, width=0.62)
    ax.bar_label(bars, labels=[f"R$ {v:,.0f}" for v in df.avg_order_value], padding=3, fontsize=10, color=INK)
    ax.set_ylim(0, df.avg_order_value.max() * 1.15)
    ax.grid(axis="x", visible=False)
    ax.set_ylabel("Average order value (R$)")
    long_plans = df[df.installment_band.str.contains("7-10|11")]
    multiple = (long_plans.revenue.sum() / long_plans.orders.sum()) / df.avg_order_value.iloc[0]
    ax.set_title(f"Card orders paid in 7+ instalments are {multiple:.1f}x larger than pay-in-full orders")
    save(fig, "10_installments_vs_order_value",
         f"Credit-card orders. 7+ instalments: {long_plans.pct_of_card_orders.sum():.1f}% of card orders, "
         f"{long_plans.pct_of_card_revenue.sum():.1f}% of card revenue. Association, not proof of cause.")


def main() -> None:
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    charts = [monthly_revenue, delivery_vs_review, late_vs_on_time, late_by_state, category_pareto,
              cohort_heatmap, rfm_segments, seller_concentration, low_review_drivers, installments]
    for chart in charts:
        chart()
    print(f"  {len(charts)} charts written to outputs/charts/")


if __name__ == "__main__":
    main()
