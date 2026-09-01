# BAsight — Frontend

Next.js client for BAsight. Talks to the FastAPI backend for cleaning, schema detection, insights, the agent and holds no business logic. It is responsible for deciding how to display what the backend returns.

## Stack

Next.js 14 (App Router), TypeScript, Tailwind, Recharts, `lucide-react`. No component library, no state management library and `useState` and prop drilling are enough for the current version.

## Setup

```bash
npm install
cp .env.local.example .env.local 
npm run dev
```

`.env.local` needs `NEXT_PUBLIC_API_URL` pointing at the backend (`http://127.0.0.1:8000` for local dev). First run needs internet access once, to fetch the Google fonts used in the design (`next/font/google`).

## State machine

`app/page.tsx` holds one piece of state, `phase: "upload" | "processing" | "ready"`, and renders one of three top-level components accordingly. There's no router involved, this is a single-page flow. `handleFileSelected` moves to `"processing"` immediately on file selection (before the network request resolves) and calls `uploadDataset`; the result or error is threaded into `ReceiptLoader`, which owns its own internal animation timing independent of when the actual response arrives. `handleReset` returns to `"upload"` and clears everything, used both by an upload error and by the dashboard's "new file" action.

## The upload → dashboard sequence

**Upload** (`UploadScreen.tsx`) validates extension and file size client-side follow the same limits the backend enforces (25MB, `.csv`/`.xlsx`/`.xls`), checked twice so a bad file gives immediate feedback.

**Processing** (`ReceiptLoader.tsx`) is the one deliberately stylized piece. It prints a fixed sequence of lines (`SCRIPTED_LINES`) at a steady 340ms interval to simulate a receipt printer, and only once that sequence finishes *and* the real API response has arrived does it print a second batch of lines built directly from that response — row count, column count, fields identified, any data-quality warnings, and the actual computed revenue total (`buildFinalLines`, driven by the same `DatasetResponse` the dashboard renders from). If the response is slow, a "still totaling" line holds until it arrives; if the response fails, the scripted animation is interrupted and an error state renders instead. This means the displayed values are always real adn timed for readability.

**Dashboard** (`Dashboard.tsx`) composes the Key Performance Indicators (KPI) row, the revenue chart, top products, category breakdown, and the chat panel from the single `DatasetResponse` object returned by upload. It also computes `currencyColumns`, a `Set` built from `schema_summary.detected_roles.price` and `.revenue`, passed down into the chat panel so it can tell a dollar figure apart from a plain count (see below).

## LLM Chat

`ChatFeed.tsx` handles the conversation: an array of `ChatTurn` (`{id, question, response, isLoading, errorMessage}`), a text input, and a busy flag that disables submission mid-request. Submitting appends a new turn in a loading state immediately, then patches it in place once `sendChatMessage` resolves or rejects — the turn list is never rebuilt from scratch, so earlier turns don't re-render. "New question" button clears local state and calls the backend's chat-reset endpoint.

### Deciding what to render (`chat/ResponseCard.tsx`)

The model's text answer is always shown first, and any successful tool calls are rendered underneath it as a sequence of visuals. The actual logic is `pickVisuals()`, which iterates through every successful tool call in the turn in order and builds a list of visual blocks

- `query_metric` with exactly one row → `InlineMetric`, a big-number card. Whether it is treated as currency is decided by checking the tool result's `metric_column` against `currencyColumns`, which is built from the dataset's detected `price` and `revenue` roles.
- `query_metric` with more than one row → `InlineChart`. If `granularity_used` is set, it is treated as a time-series chart and rendered as an area chart; otherwise it is a categorical breakdown that is rendered as a bar chart.
- `simulate_scenario` → `ScenarioComparison`, showing current vs. projected revenue, the delta, and the explicit assumption text from the backend.
- `execute_custom_analysis` → `CustomResult`, which branches on the JavaScript type of the returned value: numbers become a big-number card, arrays of objects become a small table (first 10 rows), and everything else is rendered as formatted text.
- Failed tool calls are skipped entirely; successful ones are included in order, and no successful tool call means no visual block beyond the text response.

## Types (`lib/types.ts`)

`QueryMetricData`, `SimulateScenarioData`, `CustomAnalysisData`, and `ChatToolCall`/`ChatResponse` mirror the backend's Pydantic response models field-for-field — kept manually in sync rather than generated from the OpenAPI schema, since the surface is small enough that codegen tooling isn't worth the build-step complexity yet. If a field is added to a tool's result on the backend, it needs adding here too before the frontend can use it.

## API client (`lib/api.ts`)

A thin typed wrapper around `fetch` — `uploadDataset`, `getDataset`, `getSchema`, `getInsights`, `deleteDataset`, `sendChatMessage`, `resetChat`. Every function funnels through `handleResponse`, which throws a typed `ApiError` (carrying the HTTP status) on a non-2xx response, parsed from the backend's `{"detail": "..."}` error shape when present. Nothing here retries or caches; each call is a single request.

## Design system

Built around receipts, price tags, and ledgers rather than generic dashboard chrome. The palette (`tailwind.config.ts`) is deliberately small: `ink` (`#100E0B`, the near-black background), `paper` (`#F6F1E4`, used for anything meant to read as a printed record — the receipt loader, the top-products list), one accent color `signal` (`#F0631F`, an orange used for the primary numbers and interactive states), and two purely functional colors, `mint` (`#35C488`) and `brick` (`#C1443A`), used only for positive/negative deltas — never decoratively. Every number in the UI is set in IBM Plex Mono, not the body font, so figures align the way a receipt or invoice does. Reusable structural pieces — the dashed "perforated" card edges, the barcode texture, the halftone grain — are CSS utility classes in `app/globals.css` (`.perforated-top`, `.barcode`, `.halftone`), so new components can stay visually consistent without copying markup.

## Structure

```
app/
  page.tsx              Upload -> processing -> dashboard state machine
  layout.tsx              Font loading, page metadata
  globals.css               Theme tokens + the reusable CSS utilities above

components/
  UploadScreen.tsx        Landing screen / dropzone, client-side validation
  ReceiptLoader.tsx         Upload-processing animation, driven by real response data
  Dashboard.tsx               Composes the KPI row, charts, and chat panel
  KpiCard.tsx                  Single metric, animated count-up on mount
  RevenueChart.tsx               Revenue-over-time chart
  TopProductsReceipt.tsx           Top products, receipt-styled
  CategoryBreakdown.tsx              Revenue by category
  DataQualityBanner.tsx                Surfaces backend cleaning warnings
  ChatFeed.tsx                          Conversation state, input, reset action
  chat/
    ResponseCard.tsx                      Per-turn: text always, pickVisual decides the rest
    InlineMetric.tsx                        Big-number visual
    InlineChart.tsx                           Bar or area chart
    ScenarioComparison.tsx                      Before/after for simulate_scenario
    CustomResult.tsx                              Fallback rendering for sandbox output

hooks/
  useCountUp.ts          Animates a number to its target on mount, respects
                          prefers-reduced-motion

lib/
  api.ts                 Typed fetch wrapper, one function per backend endpoint
  types.ts                 TypeScript mirrors of the backend's Pydantic models
```
