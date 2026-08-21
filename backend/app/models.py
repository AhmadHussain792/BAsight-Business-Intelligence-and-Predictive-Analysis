"""
Pydantic schemas for API request/response bodies. Keeping these
separate from the pandas-facing logic means FastAPI validates and
documents the API surface for free (see /docs).
"""
from typing import Any, Optional

from pydantic import BaseModel, Field


class ColumnSchema(BaseModel):
    name: str
    dtype: str
    role: str
    null_count: int
    null_percentage: float
    cardinality: int
    sample_values: list[Any]
    min_value: Optional[Any] = None
    max_value: Optional[Any] = None
    is_derived: bool = False


class DataQualityReport(BaseModel):
    duplicate_rows: int
    columns_with_high_nulls: list[str]
    warnings: list[str]


class SchemaResponse(BaseModel):
    row_count: int
    column_count: int
    columns: list[ColumnSchema]
    detected_roles: dict[str, str] = Field(
        default_factory=dict,
        description="Maps a semantic role (date, product, revenue, ...) to the column name filling it.",
    )
    data_quality: DataQualityReport


class TimeSeriesPoint(BaseModel):
    period: str
    revenue: float
    order_count: int


class ProductInsight(BaseModel):
    name: str
    revenue: float
    quantity: Optional[float] = None


class CategoryInsight(BaseModel):
    category: str
    revenue: float


class InsightsResponse(BaseModel):
    total_revenue: Optional[float] = None
    total_orders: int
    average_order_value: Optional[float] = None
    best_selling_product: Optional[ProductInsight] = None
    top_products: list[ProductInsight] = Field(default_factory=list)
    revenue_over_time: list[TimeSeriesPoint] = Field(default_factory=list)
    revenue_time_granularity: Optional[str] = None
    category_breakdown: list[CategoryInsight] = Field(default_factory=list)
    period_over_period_change_pct: Optional[float] = None
    unavailable_metrics: list[str] = Field(
        default_factory=list,
        description="Metrics that could not be computed, with a short reason each.",
    )


class DatasetResponse(BaseModel):
    dataset_id: str
    filename: str
    schema_summary: SchemaResponse
    insights: InsightsResponse


class DatasetListItem(BaseModel):
    dataset_id: str
    filename: str
    row_count: int
    column_count: int
    uploaded_at: str


class ErrorResponse(BaseModel):
    detail: str
