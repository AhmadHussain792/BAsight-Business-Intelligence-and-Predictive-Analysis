// Mirrors app/models.py on the backend

export interface ColumnSchema {
  name: string;
  dtype: string;
  role: string;
  null_count: number;
  null_percentage: number;
  cardinality: number;
  sample_values: unknown[];
  min_value: string | number | null;
  max_value: string | number | null;
  is_derived: boolean;
}

export interface DataQualityReport {
  duplicate_rows: number;
  columns_with_high_nulls: string[];
  warnings: string[];
}

export interface SchemaResponse {
  row_count: number;
  column_count: number;
  columns: ColumnSchema[];
  detected_roles: Record<string, string>;
  data_quality: DataQualityReport;
}

export interface TimeSeriesPoint {
  period: string;
  revenue: number;
  order_count: number;
}

export interface ProductInsight {
  name: string;
  revenue: number;
  quantity: number | null;
}

export interface CategoryInsight {
  category: string;
  revenue: number;
}

export interface InsightsResponse {
  total_revenue: number | null;
  total_orders: number;
  average_order_value: number | null;
  best_selling_product: ProductInsight | null;
  top_products: ProductInsight[];
  revenue_over_time: TimeSeriesPoint[];
  revenue_time_granularity: string | null;
  category_breakdown: CategoryInsight[];
  period_over_period_change_pct: number | null;
  unavailable_metrics: string[];
}

export interface DatasetResponse {
  dataset_id: string;
  filename: string;
  schema_summary: SchemaResponse;
  insights: InsightsResponse;
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

// --- Chat / agent types, mirroring app/agent/schemas.py and the ChatResponse model ---

export interface QueryMetricRow {
  group: string | null;
  value: number | null;
}

export interface QueryMetricData {
  ok: boolean;
  rows: QueryMetricRow[];
  matching_row_count: number | null;
  granularity_used: string | null;
  metric_column: string | null;
  trace: string;
  error: string | null;
}

export interface SimulateScenarioData {
  ok: boolean;
  baseline_revenue: number | null;
  projected_revenue: number | null;
  delta: number | null;
  delta_pct: number | null;
  rows_used: number | null;
  assumptions: string;
  trace: string;
  error: string | null;
}

export interface CustomAnalysisData {
  ok: boolean;
  result: unknown;
  error: string | null;
}

export type ToolResultData = QueryMetricData | SimulateScenarioData | CustomAnalysisData;

export interface ChatToolCall {
  name: "query_metric" | "simulate_scenario" | "execute_custom_analysis" | string;
  ok: boolean;
  summary: string;
  data: Record<string, unknown>;
}

export interface ChatResponse {
  answer: string | null;
  tool_calls: ChatToolCall[];
  hit_iteration_limit: boolean;
}

export interface ChatTurn {
  id: string;
  question: string;
  response: ChatResponse | null;
  isLoading: boolean;
  errorMessage: string | null;
}
