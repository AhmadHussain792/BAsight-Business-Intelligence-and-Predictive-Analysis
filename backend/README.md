# BAsight — Backend

This document provides an explanation about the file ingestion, cleaning, schema detection, dashboard metrics, and the chat agent (tool-calling core + sandboxed fallback).

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000

cd sandbox && npm install
```

LLM Chat needs Google Cloud auth via Application Default Credentials (ADC), not an API key:

```bash
gcloud auth application-default login          # local dev
# or, for a deployment:
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

Everything except the `/chat` endpoints works with zero configuration.

### Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated allowed frontend origins |
| `MAX_UPLOAD_SIZE_MB` | `25` | Hard cap on size of file uploaded |
| `DATASET_TTL_HOURS` | `2` | How long an uploaded dataset and its chat history stays in memory |
| `GOOGLE_CLOUD_PROJECT` | — | Required for chat |
| `GOOGLE_CLOUD_LOCATION` | `us-central1` | Vertex AI region |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Default model used by the agent |
| `GEMINI_THINKING_BUDGET` | — | Optional Gemini 2.x thinking budget override |
| `GEMINI_THINKING_LEVEL` | — | Optional Gemini 3.x thinking level override |

Note: `thinking_config` is only sent when at least one of those values is set. Gemini 2.x commonly uses `GEMINI_THINKING_BUDGET`, while Gemini 3.x uses `GEMINI_THINKING_LEVEL`.

## The data pipeline

### Ingestion (`app/ingestion.py`)

File bytes are processed to create a cleaned `pandas.DataFrame`. For CSV, the encoding is resolved by trying to read file in the order: `utf-8-sig`, `utf-8`, `cp1252`, `latin-1`. The last of which, `latin-1` is a byte-to-character mapping that never raises an error, so decoding is guaranteed to succeed even if the actual encoding is unknown. The delimiter is sniffed from the first chunk of the file rather than assumed to be a comma. Excel files go through `pandas.read_excel` directly.

Cleaning then runs column by column:

- Duplicate column names are disambiguated (pandas does this automatically on read; a secondary pass in `_dedupe_column_names` exists as a safety net for whatever leaks through).
- Fully-empty rows and columns are dropped.
- Text columns are stripped of whitespace, and empty rows (`""`, `"N/A"`, `"null"`) are normalized to `NaN`.
- Numeric coercion: currency symbols (`$£€¥`), thousands commas, `%`, and accounting-style negatives — `(12.50)` becomes `-12.50` are stripped, then the column is parsed with `pd.to_numeric`. The conversion is only kept if at least `NUMERIC_CONVERSION_THRESHOLD` (90%) of non-null values parsed successfully; otherwise the column stays as text. This is what stops a column that's mostly SKU codes with the occasional numeric-looking value from being wrongly coerced.
- Date coercion works the same way at an 80% threshold, with one extra step for day-first/month-first ambiguity. A column like `04/05/2025` can mean either 4 May or 5 April with no way to tell from that value alone. The parser scans every value in the column for one that breaks the tie: a first-position value over 12 can only be a day (`13/04/2025`), a second-position value over 12 can only mean the format is month-first. It uses whichever convention gets confirmed. If nothing in the entire column disambiguates it, day-first is assumed, and that assumption is surfaced as an explicit warning in the API response and displayed in the frontend dashboard.

This runs once at upload time; the result is what both the dashboard and every agent tool later operate on.

### Schema detection (`app/schema_detection.py`)

Every column is assigned one of the following roles: `date`, `identifier`, `revenue`, `price`, `quantity`, `customer`, `product`, `category`, or left unlabeled. Detection is name-first: the column name is normalized (lowercased, non-alphanumeric collapsed to underscores) and checked against a keyword table for each role, in priority order. Matching is token-based and `unit_price` matches `price` because `price` is a whole underscore-delimited token in it, but a column like `paid_amount` does *not* match `identifier` on the substring `"id"`, because token matching requires `"id"` to be a complete token, not a substring of `"paid"`.

If the name gives no signal, the fallback is dtype- (datatype) and cardinality-based (uniqueness): numeric columns become `numeric_other`; text columns with high cardinality relative to row count become `identifier`-like, low cardinality becomes `category`.

`detect_core_columns` reduces the full column list down to the one column filling each role (first match wins), producing the `core_columns` dict that both `insights.py` and the agent's tools utilize.

### Insights (`app/insights.py`)

It is computed once per upload and cached on the `DatasetRecord`:

- **Total revenue** — direct sum if a revenue/sales column was detected; otherwise derived as `price × quantity` per row if both of those were detected. If neither path is available, the metric is omitted with a stated reason (`unavailable_metrics` in the response), not a zero.
- **Best-selling product / top 10 products** — grouped by the product column, ranked by revenue.
- **Revenue over time** — grouped by the date column, bucketed by `pandas.resample` at a granularity chosen from the span of the date range: ≤45 days is daily, ≤180 is weekly, otherwise monthly.
- **Category breakdown** — revenue grouped by the category column.
- **Period-over-period change** — total revenue in the first half of the date range vs. the second half.

### Storage (`app/storage.py`)

In-memory, keyed by a UUID `dataset_id` generated on upload. Every request that touches a dataset looks it up by UUID, so concurrent uploads from different sessions don't interfere with each other. Entries expire after `DATASET_TTL_HOURS` that is checked when `dataset_id` is accessed. Conversation history (`app/agent/conversation_store.py`) follows the same pattern, keyed by the same `dataset_id`.

## API Endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/datasets` | Upload a CSV/XLSX and returns schema + insights |
| `GET` | `/api/datasets` | List active datasets |
| `GET` | `/api/datasets/{id}` | Re-fetch schema + insights |
| `GET` | `/api/datasets/{id}/schema` | fetch Schema only |
| `GET` | `/api/datasets/{id}/insights` | fetch Insights only |
| `DELETE` | `/api/datasets/{id}` | Drop a dataset |
| `POST` | `/api/datasets/{id}/chat` | Ask the agent a question |
| `DELETE` | `/api/datasets/{id}/chat` | Clear conversation history |
| `GET` | `/api/health` | Liveness check |

Upload validates extension against `{.csv, .xlsx, .xls}` and size against `MAX_UPLOAD_SIZE_MB` before any parsing happens; a file that parses to zero usable rows after cleaning (e.g. headers with no data) is rejected with a 400 error code rather than returning an empty dashboard.

`POST /chat` request body: `{"message": string}`. Response:

```json
{
  "answer": "string or null",
  "tool_calls": [
    { "name": "query_metric", "ok": true, "summary": "...", "data": { /* full tool result */ } }
  ],
  "hit_iteration_limit": false
}
```

`data` carries the tool's complete structured result and this is what the frontend's chat visuals are built from. Its shape depends on which tool ran; see below.

Full interactive docs at `/docs` (FastAPI's auto-generated Swagger UI) once the server is running.

## The agent

### Agentic layer breakdown

The system prompt tells the model that every number in its answer has to come from a deterministic tool result, never its own arithmetic. LLM code-generation is not the default path, and is instead a backup for when the tools fail. The reason for this is that a model that can freely write and run pandas code against the live dataset can also fabricate a number and provide it as a computation. A fixed set of typed validated tools can't.

### The three tools (`app/agent/tools.py`, `schemas.py`)

**`query_metric`** — `metric_column` (a real column name, or the literal string `"row_count"`), `aggregation` (`sum`/`mean`/`count`/`min`/`max`/`median`), optional `group_by`, optional `time_granularity` (only meaningful if `group_by` is a date column — auto-picked from the data's span if omitted), optional `filters` (a list of `{column, operator, value}`, operators `==`/`!=`/`>`/`>=`/`<`/`<=`/`in`), `sort_descending`, `limit`.

Filter values are coerced to the target column's dtype before comparing. A filter value arriving as the string `"4"` still matches an integer column. Grouped results are sorted differently depending on what was grouped: a categorical grouping is ranked by value (so "top products" works), but a date grouping is always sorted chronologically regardless of the `sort_descending` flag. If a `limit` is applied to a time series, it keeps the most recent N periods.

An invalid column name, for either `metric_column` or `group_by`, returns an error result naming the actual available columns, rather than raising. This is deliberate so the model sees the error and can retry with a corrected column name in its next tool call, which happens routinely.

**`simulate_scenario`** — `price_change_pct`, `assumed_demand_elasticity` (required, no default — the tool returns an error if it's omitted rather than assuming a value), optional `filters` to scope the simulation to a product or category. Requires both a price and a quantity column to have been detected; returns an explicit error naming what's missing otherwise. Computes baseline revenue as `sum(price × quantity)` over the (optionally filtered) rows, applies the price change to get a new price, applies `elasticity × price_change_pct` to get the resulting volume change, and returns baseline, projected, delta, delta percentage, and an `assumptions` string spelling out exactly what elasticity was used.

**`execute_custom_analysis`** — `code` (must assign its answer to a variable named `result`) and a required `reasoning` field explaining why the other two tools didn't suffice. Dispatches to the sandbox described below.

### The orchestration loop (`app/agent/orchestrator.py`)

`run_agent_turn` builds the system prompt once per conversation (the dataset's filename and its full column list including name, role, dtype, sample values so the model knows what it's working with without a separate discovery tool call), appends the user's message, and loops up to `MAX_ITERATIONS` (6) times: call the model with the tool specs, and if it returns tool calls, dispatch each one, append the result to the conversation as a tool message, and call again. The model may emit multiple tool calls in a single assistant turn; the orchestrator records each call, appends one assistant `tool_calls` payload, then appends one `tool` message per dispatched call so the model can match the results back to the request. If the model returns plain text instead of tool calls, that's the final answer and the loop ends. If the cap is hit without a final answer, the turn is reported as having hit the iteration limit rather than returning nothing or looping forever.

Bad arguments from the model (an invalid enum value, a missing required field) are caught as a Pydantic `ValidationError` and turned into a plain-English tool-result message the model can react to, the same way it reacts to any other tool error.

### The LLM client (`app/agent/llm_client.py`, `llm_factory.py`)

`LLMClient` is an interface with one method, `complete(messages, tools) -> LLMResponse`; the orchestrator only knows this interface, not which provider is behind it. `VertexAILLMClient` implements it against Google Cloud using the `google-genai` SDK (`vertexai=True`, `project`, `location`).

The translation between this project's internal message format and Gemini's own is entirely inside this client:

- There's no `system` role in Gemini's `Content` list — the system prompt is extracted from the internal message list and passed as a separate `system_instruction` config field.
- Gemini uses `user`/`model` roles, not `user`/`assistant`/`tool`. A tool-call request becomes a `model`-role `Content` with `function_call` parts; a tool result goes back as a `user`-role `Content` with a `function_response` part. Consecutive tool results are bundled into a single `user` content block so Gemini sees them as one function-response turn.
- Tool specs are Pydantic-model-derived JSON schema, passed straight through via `FunctionDeclaration`'s `parameters_json_schema` field — Gemini accepts a standard JSON schema directly, including the `$defs`/`$ref` structure Pydantic emits for the nested `FilterCondition` model, so there's no hand-written schema converter to keep in sync.
- Optional `thinking_config` is added only when `GEMINI_THINKING_BUDGET` or `GEMINI_THINKING_LEVEL` is configured, using `types.ThinkingConfig(...)` before the model call.

An `OpenAILLMClient` exists behind the same interface. It is unused by `llm_factory.py` by default.

## The sandbox

`execute_custom_analysis`'s code never runs inside the FastAPI process. `app/agent/sandbox.py` serializes the dataset to CSV, spawns `sandbox/entrypoint.mjs` as a subprocess, and reads back a JSON result over stdout.

```
FastAPI process
  -> subprocess: node sandbox/entrypoint.mjs         [stdin/stdout JSON, outer timeout]
     -> worker_thread: sandbox/pyodide_worker.mjs      [inner hard timeout via terminate()]
        -> Pyodide (Python compiled to WebAssembly), running only the model's code
```

Three isolation properties hold regardless of what the code tries to do:

- **No host filesystem access.** Pyodide's Python `open()` operates on an in-memory virtual filesystem specific to that WASM instance, not the real disk.
- **No network access.** There's no fetch/socket bridge exposed to the code running inside.
- **No host secrets.** The worker thread is spawned with an empty environment (`env: {}`), and the `js`/`pyodide_js`/`micropip` modules — which would otherwise let code reach back into the Node host, including its real environment variables — are blocked from being imported at all, as a second layer on top of the empty environment.

**Timeout enforcement is dual-layered**: a same-thread, cooperative timeout (a JS `Promise.race` against a `setTimeout`) cannot interrupt a tight loop running inside a synchronous WASM call, because that loop never yields control back to the event loop for the timer callback to fire. The only thing that reliably stops it is external termination — `entrypoint.mjs` calls `Worker.terminate()` on the worker thread from outside it after the deadline, which works because it tears down the underlying V8 isolate rather than asking the code inside to stop. `app/agent/sandbox.py` adds a second, looser `subprocess.run(timeout=...)` around the whole Node process as a backstop in case the inner mechanism doesn't fire for some reason not yet encountered.

The executed code must assign its answer to a variable named `result` — plain values, or a pandas Series/DataFrame/NumPy scalar, which get converted to JSON automatically. `df`, `pandas`, and `numpy` are available inside; `pandas`/`numpy` are loaded into the Pyodide runtime from its package CDN at request time, which means the sandbox needs outbound network access from the *host* side (not from inside the isolated code — that's still blocked) to function at all.