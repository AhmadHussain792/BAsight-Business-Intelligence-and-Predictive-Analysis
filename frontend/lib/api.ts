import { ApiError, DatasetResponse, InsightsResponse, SchemaResponse } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = `Request failed with status ${response.status}.`;
    try {
      const body = await response.json();
      if (body?.detail) detail = body.detail;
    } catch {
      // response wasn't JSON — fall back to the generic message above
    }
    throw new ApiError(detail, response.status);
  }
  return response.json() as Promise<T>;
}

export async function uploadDataset(file: File): Promise<DatasetResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${API_BASE}/api/datasets`, {
    method: "POST",
    body: formData,
  });
  return handleResponse<DatasetResponse>(response);
}

export async function getDataset(datasetId: string): Promise<DatasetResponse> {
  const response = await fetch(`${API_BASE}/api/datasets/${datasetId}`);
  return handleResponse<DatasetResponse>(response);
}

export async function getSchema(datasetId: string): Promise<SchemaResponse> {
  const response = await fetch(`${API_BASE}/api/datasets/${datasetId}/schema`);
  return handleResponse<SchemaResponse>(response);
}

export async function getInsights(datasetId: string): Promise<InsightsResponse> {
  const response = await fetch(`${API_BASE}/api/datasets/${datasetId}/insights`);
  return handleResponse<InsightsResponse>(response);
}

export async function deleteDataset(datasetId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/api/datasets/${datasetId}`, { method: "DELETE" });
  await handleResponse(response);
}
