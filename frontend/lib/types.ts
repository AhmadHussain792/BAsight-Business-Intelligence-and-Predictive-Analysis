// Mirrors app/models.py on the backend. Keep in sync manually — small
// enough surface area that generating this from the OpenAPI schema isn't
// worth the build-step complexity yet.

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
