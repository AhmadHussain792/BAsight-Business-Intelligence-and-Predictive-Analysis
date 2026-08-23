"""
The agentic loop: given a dataset and a conversation, calls the LLM with
the tool specs, dispatches whatever tools it asks for against the real
DataFrame, feeds results back, and repeats until the model gives a final
text answer or a safety iteration cap is hit.

Design choices worth calling out:
  - Every tool call is dispatched through a fixed dict, never eval'd or
    dynamically resolved from the model's output — an unknown tool name
    is an error result fed back to the model, not a lookup into anything
    that could be pointed somewhere unintended.
  - Bad arguments (wrong enum value, missing required field) are caught as
    a Pydantic ValidationError and turned into a plain-English tool-result
    error, not an exception that aborts the turn — the model can see what
    was wrong and retry, the same way a human would react to an API 400.
  - max_iterations bounds runaway tool-call loops (cost + latency), and is
    reported distinctly from a normal answer so the caller can tell the
    difference between "here's the answer" and "gave up after N tool calls".
"""
from dataclasses import dataclass, field
from typing import Callable

from pydantic import ValidationError

from .llm_client import LLMClient
from .schemas import ExecuteCustomAnalysisArgs, QueryMetricArgs, SimulateScenarioArgs
from .tool_specs import TOOL_SPECS
from .tools import execute_custom_analysis, query_metric, simulate_scenario
from ..models import SchemaResponse
from ..storage import DatasetRecord

MAX_ITERATIONS = 6

SYSTEM_PROMPT_TEMPLATE = """You are a data analyst assistant working with one specific dataset: {filename}.

Columns available (name — role — dtype — sample values):
{column_summary}

Rules:
- Every number in your answer must come from a tool result. Never compute or estimate a
  figure yourself — call query_metric (or simulate_scenario for what-if pricing questions).
- Only use execute_custom_analysis when query_metric and simulate_scenario genuinely can't
  express the question (e.g. correlation, outlier detection). State why in `reasoning`.
- simulate_scenario requires an explicit demand elasticity. If the user hasn't given you one,
  ask them, or use a clearly-labeled conservative default (e.g. -0.5) and say plainly in your
  answer that it's an assumption, not a fact derived from their data.
- If a tool call fails (unknown column, bad filter), don't guess a fix silently — either
  correct it using the column list above, or tell the user what's missing.
- Be concise. State the number, cite the timeframe/filter briefly, skip preamble.
"""


@dataclass
class ToolCallRecord:
    name: str
    arguments: dict
    ok: bool
    summary: str


@dataclass
class AgentTurnResult:
    answer: str | None
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    hit_iteration_limit: bool = False
    messages: list[dict] = field(default_factory=list)  # full updated history, to persist


def _build_system_prompt(record: DatasetRecord) -> str:
    lines = []
    for col in record.columns:
        samples = ", ".join(str(s) for s in col.sample_values[:3])
        lines.append(f"- {col.name} — {col.role} — {col.dtype} — e.g. [{samples}]")
    return SYSTEM_PROMPT_TEMPLATE.format(filename=record.filename, column_summary="\n".join(lines))


def _dispatch_tool(name: str, arguments: dict, record: DatasetRecord) -> tuple[str, bool]:
    """Returns (result_text_for_llm, ok). Never raises — any failure becomes
    a result the model can react to."""
    try:
        if name == "query_metric":
            args = QueryMetricArgs.model_validate(arguments)
            result = query_metric(record.df, args)
        elif name == "simulate_scenario":
            args = SimulateScenarioArgs.model_validate(arguments)
            result = simulate_scenario(record.df, record.core_columns, args)
        elif name == "execute_custom_analysis":
            args = ExecuteCustomAnalysisArgs.model_validate(arguments)
            result = execute_custom_analysis(record.df, args.code)
        else:
            return f"Unknown tool '{name}'. Available tools: query_metric, simulate_scenario, execute_custom_analysis.", False
    except ValidationError as e:
        return f"Invalid arguments for {name}: {e}", False

    return result.model_dump_json(), result.ok


def run_agent_turn(
    llm: LLMClient,
    record: DatasetRecord,
    history: list[dict],
    user_message: str,
) -> AgentTurnResult:
    messages = list(history)
    if not messages:
        messages.append({"role": "system", "content": _build_system_prompt(record)})
    messages.append({"role": "user", "content": user_message})

    tool_call_log: list[ToolCallRecord] = []

    for _ in range(MAX_ITERATIONS):
        response = llm.complete(messages, TOOL_SPECS)

        if not response.wants_tool_calls:
            messages.append({"role": "assistant", "content": response.text or ""})
            return AgentTurnResult(answer=response.text, tool_calls=tool_call_log, messages=messages)

        # OpenAI's protocol: the assistant message carrying tool_calls goes in
        # first, then one role="tool" message per call, each tagged with its
        # tool_call_id so the model can match results back to its requests.
        messages.append(
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": _json_dumps(tc.arguments)},
                    }
                    for tc in response.tool_calls
                ],
            }
        )

        for tc in response.tool_calls:
            result_text, ok = _dispatch_tool(tc.name, tc.arguments, record)
            tool_call_log.append(ToolCallRecord(name=tc.name, arguments=tc.arguments, ok=ok, summary=result_text[:300]))
            messages.append({"role": "tool", "tool_call_id": tc.id, "name": tc.name, "content": result_text})

    return AgentTurnResult(answer=None, tool_calls=tool_call_log, hit_iteration_limit=True, messages=messages)


def _json_dumps(d: dict) -> str:
    import json

    return json.dumps(d)
