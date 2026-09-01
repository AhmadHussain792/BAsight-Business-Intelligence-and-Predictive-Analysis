"""
Heuristic semantic-role detection for columns: figures out which
column is "the date", "the product", "the revenue", etc. so the
insights layer doesn't need to know a dataset's exact schema ahead
of time.
This is name-keyword-first, dtype-second. ML-based schema detection is an upgrade 
path to let the LLM confirm/correct ambiguous cases.
"""
import re

import numpy as np
import pandas as pd

from .config import settings
from .dtype_utils import is_textual_dtype
from .models import ColumnSchema, DataQualityReport

ROLE_KEYWORDS: dict[str, list[str]] = {
    "date": ["date", "time", "timestamp", "period", "order_date", "purchase_date"],
    "identifier": ["id", "uuid", "order_id", "transaction_id", "invoice", "receipt"],
    "product": ["product", "item", "sku", "product_name", "description"],
    "category": ["category", "type", "segment", "department", "class", "genre"],
    "quantity": ["quantity", "qty", "units", "unit_count", "volume_sold"],
    "price": ["unit_price", "price", "unit_cost", "cost", "rate"],
    "revenue": ["revenue", "sales", "total", "amount", "total_sales", "turnover", "gross"],
    "customer": ["customer", "client", "buyer", "customer_id", "user_id"],
}

# Order matters: checked top-to-bottom, first match wins for name-based detection
ROLE_PRIORITY = ["date", "identifier", "revenue", "price", "quantity", "customer", "product", "category"]

# token-based keyword matching: "unit_price matched to "price" due to token "price"
def _match_role_by_name(column_name: str) -> str | None:
    normalized = re.sub(r"[^a-z0-9]+", "_", column_name.lower()).strip("_")
    tokens = set(normalized.split("_"))
    padded = f"_{normalized}_"

    for role in ROLE_PRIORITY:
        for keyword in ROLE_KEYWORDS[role]:
            if "_" in keyword:
                if f"_{keyword}_" in padded:
                    return role
            elif keyword in tokens:
                return role
    return None


def infer_column_role(column_name: str, series: pd.Series) -> str:
    name_match = _match_role_by_name(column_name)

    if pd.api.types.is_datetime64_any_dtype(series):
        return "date"

    if name_match == "date":
        return "date"

    if name_match in {"revenue", "price", "quantity"}:
        if pd.api.types.is_numeric_dtype(series):
            return name_match

    if name_match in {"identifier", "customer", "product", "category"}:
        return name_match

    # fallback heuristics when the column name gives no hint.
    if pd.api.types.is_numeric_dtype(series):
        return "numeric_other"

    if is_textual_dtype(series) or isinstance(series.dtype, pd.CategoricalDtype):
        non_null = series.dropna()
        if non_null.empty:
            return "unknown"
        cardinality_ratio = non_null.nunique() / len(non_null)
        if cardinality_ratio > 0.9:
            return "identifier"
        if cardinality_ratio < 0.5:
            return "category"
        return "text"

    return "unknown"


def _safe_sample_values(series: pd.Series, n: int = 3) -> list:
    non_null = series.dropna()
    if non_null.empty:
        return []
    samples = non_null.drop_duplicates().head(n).tolist()
    # convert pandas/numpy scalars to native Python types for JSON-safety
    cleaned = []
    for v in samples:
        if isinstance(v, (pd.Timestamp,)):
            cleaned.append(v.isoformat())
        elif isinstance(v, (np.integer,)):
            cleaned.append(int(v))
        elif isinstance(v, (np.floating,)):
            cleaned.append(float(v))
        else:
            cleaned.append(v)
    return cleaned


def _safe_bound(value) -> object | None:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    return value


def build_column_schema(df: pd.DataFrame) -> list[ColumnSchema]:
    columns: list[ColumnSchema] = []
    row_count = len(df)

    for col in df.columns:
        series = df[col]
        null_count = int(series.isna().sum())
        role = infer_column_role(col, series)

        min_value = max_value = None
        if pd.api.types.is_numeric_dtype(series) or pd.api.types.is_datetime64_any_dtype(series):
            non_null = series.dropna()
            if not non_null.empty:
                min_value = _safe_bound(non_null.min())
                max_value = _safe_bound(non_null.max())

        columns.append(
            ColumnSchema(
                name=col,
                dtype=str(series.dtype),
                role=role,
                null_count=null_count,
                null_percentage=round(null_count / row_count * 100, 2) if row_count else 0.0,
                cardinality=int(series.nunique(dropna=True)),
                sample_values=_safe_sample_values(series),
                min_value=min_value,
                max_value=max_value,
            )
        )
    return columns

# picks and returns one column per semantic role (first match) for use by the insights layer
def detect_core_columns(columns: list[ColumnSchema]) -> dict[str, str]:
    core: dict[str, str] = {}
    for role in ["date", "product", "category", "quantity", "price", "revenue", "customer", "identifier"]:
        for col in columns:
            if col.role == role and role not in core:
                core[role] = col.name
                break
    return core


def build_data_quality_report(df: pd.DataFrame, columns: list[ColumnSchema]) -> DataQualityReport:
    high_null_cols = [
        c.name for c in columns if c.null_percentage / 100 >= settings.HIGH_NULL_WARNING_THRESHOLD
    ]
    duplicate_rows = int(df.duplicated().sum())

    warnings: list[str] = []
    if duplicate_rows:
        warnings.append(f"{duplicate_rows} duplicate row(s) detected.")
    for col_name in high_null_cols:
        pct = next(c.null_percentage for c in columns if c.name == col_name)
        warnings.append(f"Column '{col_name}' is {pct}% missing.")

    return DataQualityReport(
        duplicate_rows=duplicate_rows,
        columns_with_high_nulls=high_null_cols,
        warnings=warnings,
    )
