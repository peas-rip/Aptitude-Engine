/**
 * Typed contract STUBS for the BLOCKED admin endpoints — copied from
 * `docs/API_CONTRACTS.md` §1.2–§1.6.
 *
 * None of these endpoints exist in this backend: calling them returns 404.
 * The interfaces live here so that wiring the real screens later is
 * mechanical. **Do not invent sample data to render against them.**
 */

/** POST /api/v1/batches — multipart/form-data (file + optional config), 202. */
export interface CreateBatchResponse {
  batch_id: string;
  status: "queued";
  status_url: string;
  results_url: string;
  review_url: string;
}

/** GET /api/v1/batches/{batch_id} */
export interface BatchProgress {
  total: number;
  processed: number;
  successful: number;
  failed: number;
  needs_review: number;
}

export interface BatchStatus {
  batch_id: string;
  status: "queued" | "running" | "completed" | "failed";
  progress: BatchProgress;
  started_at: string;
  estimated_completion?: string | null;
  total_tokens?: number;
  estimated_cost_usd?: number;
}

/** GET /api/v1/batches/{batch_id}/review */
export interface ReviewItem {
  question_id: string;
  reason_codes: string[];
  question_preview: Record<string, unknown>;
  validation_errors: Array<Record<string, unknown>>;
}

export interface ReviewQueue {
  items: ReviewItem[];
  total: number;
}

/** GET /api/v1/metrics — §1.6 names the route but specifies no body. */
export interface Metrics {
  [field: string]: number | string | boolean | null;
}
