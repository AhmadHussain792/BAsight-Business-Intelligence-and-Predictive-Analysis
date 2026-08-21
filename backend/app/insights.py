"""
Computes the dashboard metrics from a cleaned DataFrame + detected
core columns. Every metric degrades gracefully: if a required column
role wasn't found, the metric is omitted and a human-readable reason
is added to `unavailable_metrics` instead of raising.
"""
import pandas as pd

from .models import CategoryInsight, InsightsResponse, ProductInsight, TimeSeriesPoint

TOP_N_PRODUCTS = 10


def _ensure_revenue_column(df: pd.DataFrame, core: dict[str, str]) -> tuple[pd.DataFrame, dict[str, str]]:
    """If there's no explicit revenue column but price and quantity both
    exist, derive one. Returns a (possibly) modified copy of df and core."""
    if "revenue" in core:
        return df, core

    if "price" in core and "quantity" in core:
        df = df.copy()
        derived_col = "_derived_revenue"
        df[derived_col] = df[core["price"]] * df[core["quantity"]]
        core = {**core, "revenue": derived_col}

    return df, core


def _pick_time_granularity(date_series: pd.Series) -> tuple[str, str]:
    """Returns (pandas resample rule, human label) based on the span of
    the date range, so a 3-day dataset isn't bucketed by month and a
    3-year dataset isn't plotted daily."""
    span_days = (date_series.max() - date_series.min()).days
    if span_days <= 45:
        return "D", "daily"
    if span_days <= 180:
        return "W", "weekly"
    return "ME", "monthly"  # 'ME' = month-end anchor; pandas deprecated bare 'M' in 2.2+


def compute_insights(df: pd.DataFrame, core_columns: dict[str, str]) -> InsightsResponse:
    unavailable: list[str] = []
    df, core = _ensure_revenue_column(df, core_columns)

    total_orders = int(len(df))
    total_revenue = None
    average_order_value = None
    best_selling_product = None
    top_products: list[ProductInsight] = []
    revenue_over_time: list[TimeSeriesPoint] = []
    granularity = None
    category_breakdown: list[CategoryInsight] = []
    period_change_pct = None

    if "revenue" in core:
        revenue_col = core["revenue"]
        valid_revenue = df[revenue_col].dropna()
        total_revenue = float(valid_revenue.sum())
        if total_orders:
            average_order_value = float(total_revenue / total_orders)
    else:
        unavailable.append(
            "total_revenue/average_order_value: no revenue column found, "
            "and none could be derived (need either a revenue/sales/amount "
            "column, or both a price and a quantity column)."
        )

    product_col = core.get("product")
    if product_col and "revenue" in core:
        grouped = (
            df.groupby(product_col, dropna=True)[core["revenue"]]
            .sum()
            .sort_values(ascending=False)
        )
        quantity_by_product = None
        if "quantity" in core:
            quantity_by_product = df.groupby(product_col, dropna=True)[core["quantity"]].sum()

        for name, revenue in grouped.head(TOP_N_PRODUCTS).items():
            qty = float(quantity_by_product.get(name)) if quantity_by_product is not None and name in quantity_by_product else None
            top_products.append(ProductInsight(name=str(name), revenue=float(revenue), quantity=qty))

        if top_products:
            best_selling_product = top_products[0]
    elif not product_col:
        unavailable.append("top_products/best_selling_product: no product/item column detected.")

    date_col = core.get("date")
    if date_col and "revenue" in core:
        ts_df = df[[date_col, core["revenue"]]].dropna()
        if not ts_df.empty:
            rule, granularity = _pick_time_granularity(ts_df[date_col])
            grouped = (
                ts_df.set_index(date_col)
                .resample(rule)[core["revenue"]]
                .agg(["sum", "count"])
                .reset_index()
            )
            for _, row in grouped.iterrows():
                revenue_over_time.append(
                    TimeSeriesPoint(
                        period=row[date_col].strftime("%Y-%m-%d"),
                        revenue=float(row["sum"]),
                        order_count=int(row["count"]),
                    )
                )

            # Period-over-period: compare first half vs second half of the
            # date range by total revenue.
            midpoint = ts_df[date_col].min() + (ts_df[date_col].max() - ts_df[date_col].min()) / 2
            first_half = ts_df[ts_df[date_col] <= midpoint][core["revenue"]].sum()
            second_half = ts_df[ts_df[date_col] > midpoint][core["revenue"]].sum()
            if first_half > 0:
                period_change_pct = round((second_half - first_half) / first_half * 100, 2)
    elif not date_col:
        unavailable.append("revenue_over_time/period_over_period_change: no date column detected.")

    category_col = core.get("category")
    if category_col and "revenue" in core:
        grouped = (
            df.groupby(category_col, dropna=True)[core["revenue"]]
            .sum()
            .sort_values(ascending=False)
        )
        category_breakdown = [
            CategoryInsight(category=str(name), revenue=float(revenue)) for name, revenue in grouped.items()
        ]

    return InsightsResponse(
        total_revenue=total_revenue,
        total_orders=total_orders,
        average_order_value=average_order_value,
        best_selling_product=best_selling_product,
        top_products=top_products,
        revenue_over_time=revenue_over_time,
        revenue_time_granularity=granularity,
        category_breakdown=category_breakdown,
        period_over_period_change_pct=period_change_pct,
        unavailable_metrics=unavailable,
    )
