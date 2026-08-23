"""
Tool specs in OpenAI's function-calling format, derived from the Pydantic
argument schemas in schemas.py rather than hand-written separately — so a
field added there shows up here automatically instead of silently drifting
out of sync with what the tool functions actually accept.
"""
from .schemas import ExecuteCustomAnalysisArgs, QueryMetricArgs, SimulateScenarioArgs

QUERY_METRIC_DESCRIPTION = (
    "Aggregate a numeric column (sum/mean/count/min/max/median), optionally grouped by another "
    "column (categorical, or a date column for a time trend) and/or filtered. Use this for almost "
    "everything: totals, averages, top-N breakdowns, trends over time, filtered counts."
)

SIMULATE_SCENARIO_DESCRIPTION = (
    "Project revenue impact of a hypothetical price change, given an explicit assumed demand "
    "elasticity. Requires both a price and a quantity column to exist in the dataset. Never guesses "
    "an elasticity silently — always pass one, sourced from the user's stated assumption or a "
    "clearly-labeled conservative default."
)

EXECUTE_CUSTOM_ANALYSIS_DESCRIPTION = (
    "Last resort: write pandas/numpy code to answer something query_metric and simulate_scenario "
    "genuinely cannot express (e.g. correlation between two columns, an outlier detection method, a "
    "multi-step derived computation). Runs in an isolated sandbox with no access to the real backend, "
    "network, or filesystem. Must assign the answer to a variable named `result`. Try the other two "
    "tools first — most questions don't need this."
)


def _to_openai_tool(name: str, description: str, model) -> dict:
    schema = model.model_json_schema()
    # Pydantic emits $defs for nested models (FilterCondition); OpenAI's tool
    # schema validator wants a single flat object, so nested refs are fine to
    # leave as-is — OpenAI resolves internal $ref/$defs correctly.
    schema.pop("title", None)
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": schema,
        },
    }


TOOL_SPECS = [
    _to_openai_tool("query_metric", QUERY_METRIC_DESCRIPTION, QueryMetricArgs),
    _to_openai_tool("simulate_scenario", SIMULATE_SCENARIO_DESCRIPTION, SimulateScenarioArgs),
    _to_openai_tool("execute_custom_analysis", EXECUTE_CUSTOM_ANALYSIS_DESCRIPTION, ExecuteCustomAnalysisArgs),
]
