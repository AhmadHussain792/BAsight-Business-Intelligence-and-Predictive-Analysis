"""
Each tool takes the real cleaned DataFrame plus validated arguments, and returns 
a result object that either carries a value or a plain-English error. 
the error is used by LLM for self-correction.

Every result includes a `trace` string: an exact, description of
what was computed (columns, filters, aggregation) to ensure 
chat answer follows real arithmetic instead of LLM hallucination
>>>>>>> b485336 (Added visuals such as charts, stylized texts, etc for each tool call in the LLM response to enhance user experience. Updated Vertex AI client to enable config of model's thinking capacity for both 2.x and 3.x generations. Wrote detailed README.md for the project)
"""
import pandas as pd

from .schemas import (
    CustomAnalysisResult,
    FilterCondition,
    QueryMetricArgs,
    QueryMetricResult,
    QueryMetricResultRow,
    SimulateScenarioArgs,
    SimulateScenarioResult,
)
from .sandbox import run_sandboxed_code

_GRANULARITY_RULES = {"day": "D", "week": "W", "month": "ME"}


def _pick_granularity(date_series: pd.Series) -> tuple[str, str]:
    non_null = date_series.dropna()
    if non_null.empty:
        return "D", "day"
    span_days = (non_null.max() - non_null.min()).days
    if span_days <= 45:
        return "D", "day"
    if span_days <= 180:
        return "W", "week"
    return "ME", "month"


def _coerce_value(series: pd.Series, value):

    # coercion of a filter value to the column's actual dtype
    if pd.api.types.is_datetime64_any_dtype(series):
        try:
            return pd.to_datetime(value)
        except (ValueError, TypeError):
            return value
    if pd.api.types.is_numeric_dtype(series):
        try:
            return float(value)
        except (ValueError, TypeError):
            return value
    return value


def _apply_filter(df: pd.DataFrame, condition: FilterCondition) -> tuple[pd.DataFrame | None, str | None]:
    if condition.column not in df.columns:
        return None, f"Unknown column '{condition.column}'. Available columns: {', '.join(df.columns)}."

    series = df[condition.column]

    if condition.operator == "in":
        if not isinstance(condition.value, list):
            return None, "The 'in' operator requires a list value."
        coerced = [_coerce_value(series, v) for v in condition.value]
        return df[series.isin(coerced)], None

    value = _coerce_value(series, condition.value)
    ops = {
        "==": lambda s, v: s == v,
        "!=": lambda s, v: s != v,
        ">": lambda s, v: s > v,
        ">=": lambda s, v: s >= v,
        "<": lambda s, v: s < v,
        "<=": lambda s, v: s <= v,
    }
    try:
        mask = ops[condition.operator](series, value)
    except TypeError as e:
        return None, f"Could not compare column '{condition.column}' to {condition.value!r}: {e}"
    return df[mask], None


def query_metric(df: pd.DataFrame, args: QueryMetricArgs) -> QueryMetricResult:
    working = df
    trace_parts: list[str] = []

    for condition in args.filters or []:
        working, err = _apply_filter(working, condition)
        if err:
            return QueryMetricResult(ok=False, error=err)
        trace_parts.append(f"{condition.column} {condition.operator} {condition.value!r}")

    is_row_count = args.metric_column == "row_count"
    if not is_row_count:
        if args.metric_column not in working.columns:
            return QueryMetricResult(
                ok=False,
                error=f"Unknown column '{args.metric_column}'. Available columns: {', '.join(df.columns)}.",
            )
        if args.aggregation != "count" and not pd.api.types.is_numeric_dtype(working[args.metric_column]):
            return QueryMetricResult(
                ok=False,
                error=f"Column '{args.metric_column}' is not numeric, so '{args.aggregation}' isn't meaningful on it. Try aggregation='count' instead.",
            )

    filter_desc = f" filtered by ({' AND '.join(trace_parts)})" if trace_parts else ""
    metric_desc = "row count" if is_row_count else f"{args.aggregation}({args.metric_column})"

    if args.group_by:
        if args.group_by not in working.columns:
            return QueryMetricResult(
                ok=False,
                error=f"Unknown group_by column '{args.group_by}'. Available columns: {', '.join(df.columns)}.",
            )
        group_series = working[args.group_by]
        granularity_used = None

        is_time_series = pd.api.types.is_datetime64_any_dtype(group_series)

        if is_time_series:
            if args.time_granularity:
                rule, granularity_used = _GRANULARITY_RULES[args.time_granularity], args.time_granularity
            else:
                rule, granularity_used = _pick_granularity(group_series)
            valid = working.dropna(subset=[args.group_by])
            grouped = valid.set_index(args.group_by).resample(rule)
            group_label = lambda k: k.strftime("%Y-%m-%d")  # noqa: E731
        else:
            grouped = working.groupby(args.group_by, dropna=True)
            group_label = str

        if is_row_count:
            agg_series = grouped.size()
        else:
            agg_series = grouped[args.metric_column].agg(args.aggregation)

        rows = [
            QueryMetricResultRow(group=group_label(k), value=None if pd.isna(v) else float(v))
            for k, v in agg_series.items()
        ]


        if is_time_series:
            # sorting a time series by value mixes the x-axis into a meaningless order for both a chart and any explanation built from these rows
            # ISO date strings (YYYY-MM-DD) do not need parsing as they sort as plain strings
            rows.sort(key=lambda r: r.group or "")
            if args.limit:
                # show most recent N as "show me last N weeks" is more common for analytics
                rows = rows[-args.limit :]
        else:
            rows.sort(key=lambda r: (r.value is not None, r.value), reverse=args.sort_descending)
            if args.limit:
                rows = rows[: args.limit]

        trace = f"{metric_desc} grouped by {args.group_by}{filter_desc}"
        if granularity_used:
            trace += f" ({granularity_used} buckets)"
        return QueryMetricResult(

            ok=True,
            rows=rows,
            matching_row_count=len(working),
            granularity_used=granularity_used,
            metric_column=None if is_row_count else args.metric_column,
            trace=trace,
        )

    value = len(working) if is_row_count else working[args.metric_column].agg(args.aggregation)
    value = None if (value is None or pd.isna(value)) else float(value)
    return QueryMetricResult(
        ok=True,
        rows=[QueryMetricResultRow(group=None, value=value)],
        matching_row_count=len(working),

        metric_column=None if is_row_count else args.metric_column,
        trace=f"{metric_desc}{filter_desc}",
    )


def simulate_scenario(df: pd.DataFrame, core_columns: dict[str, str], args: SimulateScenarioArgs) -> SimulateScenarioResult:
    if "price" not in core_columns or "quantity" not in core_columns:
        missing = [r for r in ("price", "quantity") if r not in core_columns]
        return SimulateScenarioResult(
            ok=False,
            error=f"Can't simulate a price/volume scenario: no {' or '.join(missing)} column was detected in this dataset.",
        )

    working = df
    trace_parts: list[str] = []
    for condition in args.filters or []:
        working, err = _apply_filter(working, condition)
        if err:
            return SimulateScenarioResult(ok=False, error=err)
        trace_parts.append(f"{condition.column} {condition.operator} {condition.value!r}")

    price_col, qty_col = core_columns["price"], core_columns["quantity"]
    valid = working[[price_col, qty_col]].dropna()
    if valid.empty:
        return SimulateScenarioResult(ok=False, error="No rows with both price and quantity available after filters.")

    baseline_revenue = float((valid[price_col] * valid[qty_col]).sum())
    new_price = valid[price_col] * (1 + args.price_change_pct / 100)
    volume_change_pct = args.assumed_demand_elasticity * args.price_change_pct
    new_qty = (valid[qty_col] * (1 + volume_change_pct / 100)).clip(lower=0)
    projected_revenue = float((new_price * new_qty).sum())
    delta = projected_revenue - baseline_revenue
    delta_pct = (delta / baseline_revenue * 100) if baseline_revenue else None

    filter_desc = f" scoped to ({' AND '.join(trace_parts)})" if trace_parts else " across the full dataset"
    assumptions = (
        f"Applied a {args.price_change_pct:+.1f}% price change with an assumed demand elasticity of "
        f"{args.assumed_demand_elasticity} (a 1% price change moves volume by "
        f"{args.assumed_demand_elasticity:+.2f}%). This elasticity is an assumption, not derived from the data — "
        f"state it plainly to the user rather than presenting the projection as certain."
    )
    return SimulateScenarioResult(
        ok=True,
        baseline_revenue=baseline_revenue,
        projected_revenue=projected_revenue,
        delta=delta,
        delta_pct=delta_pct,
        rows_used=len(valid),
        assumptions=assumptions,

        trace=(
            f"Simulated {args.price_change_pct:+.1f}% price change "
            f"(elasticity {args.assumed_demand_elasticity:+.2f}){filter_desc}, {len(valid)} rows used"
        ),
    )


def execute_custom_analysis(df: pd.DataFrame, code: str) -> CustomAnalysisResult:
    csv_data = df.to_csv(index=False)
    outcome = run_sandboxed_code(code=code, csv_data=csv_data, timeout_ms=15000)
    if not outcome.ok:
        return CustomAnalysisResult(ok=False, error=outcome.error)

    return CustomAnalysisResult(ok=True, result=outcome.result)