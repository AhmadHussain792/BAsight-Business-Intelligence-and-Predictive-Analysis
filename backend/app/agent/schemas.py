"""
Typed argument/result schemas for every agent tool. The argument schemas
double as the JSON-schema source for function-calling (see tool_specs.py) —
defining them once here and deriving the LLM-facing spec from them keeps
the two from drifting apart.
"""
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

Operator = Literal["==", "!=", ">", ">=", "<", "<=", "in"]
Aggregation = Literal["sum", "mean", "count", "min", "max", "median"]
Granularity = Literal["day", "week", "month"]


class FilterCondition(BaseModel):
    column: str
    operator: Operator
    value: Any = Field(description="A single value, except for 'in' which takes a list.")


class QueryMetricArgs(BaseModel):
    metric_column: str = Field(description="A numeric column name, or the literal 'row_count' to count matching rows.")
    aggregation: Aggregation = "sum"
    group_by: Optional[str] = Field(default=None, description="Column to group by — categorical or a date column.")
    time_granularity: Optional[Granularity] = Field(
        default=None, description="Only used when group_by is a date column; auto-picked from the data's span if omitted."
    )
    filters: Optional[list[FilterCondition]] = None
    sort_descending: bool = True
    limit: Optional[int] = Field(default=None, description="Cap the number of groups returned, after sorting.")


class SimulateScenarioArgs(BaseModel):
    price_change_pct: float = Field(description="e.g. 15 for a +15% price change, -10 for a -10% change.")
    assumed_demand_elasticity: float = Field(
        description=(
            "Required, not optional — this tool will not silently guess. "
            "e.g. -0.5 means a 1% price rise causes a 0.5% volume drop. "
            "Ask the user for their assumption if they have one; otherwise state "
            "a conservative default explicitly in your answer as an assumption, not a fact."
        )
    )
    filters: Optional[list[FilterCondition]] = Field(
        default=None, description="Scope the simulation, e.g. to one product or category."
    )


class ExecuteCustomAnalysisArgs(BaseModel):
    reasoning: str = Field(description="Why none of the other tools could answer this — required so this stays a deliberate fallback, not a default.")
    code: str = Field(description="Python/pandas code. Must assign the answer to a variable named `result` (JSON-serializable). `df`, `pd`, and `np` are available.")


class QueryMetricResultRow(BaseModel):
    group: Optional[str] = None
    value: Optional[float] = None


class QueryMetricResult(BaseModel):
    ok: bool
    rows: list[QueryMetricResultRow] = Field(default_factory=list)
    matching_row_count: Optional[int] = None
    granularity_used: Optional[str] = None
    trace: str = ""
    error: Optional[str] = None


class SimulateScenarioResult(BaseModel):
    ok: bool
    baseline_revenue: Optional[float] = None
    projected_revenue: Optional[float] = None
    delta: Optional[float] = None
    delta_pct: Optional[float] = None
    rows_used: Optional[int] = None
    assumptions: str = ""
    trace: str = ""
    error: Optional[str] = None


class CustomAnalysisResult(BaseModel):
    ok: bool
    result: Any = None
    error: Optional[str] = None
