import { BlockedPanel } from "../../components/BlockedPanel";
import type { CreateBatchResponse, BatchStatus } from "../../types/admin";

/**
 * Batch upload / progress / results — BLOCKED (spec §8.9).
 *
 * Intended flow once the backend lands:
 *   file drop → POST /api/v1/batches (multipart) → CreateBatchResponse
 *             → poll GET  /api/v1/batches/{id} (BatchStatus)
 *             → stream GET /api/v1/batches/{id}/results (application/x-ndjson)
 *
 * These types are the contract stub; no rows are rendered because no data
 * exists.
 */
export default function AdminBatches() {
  void (0 as unknown as CreateBatchResponse);
  void (0 as unknown as BatchStatus);

  return (
    <BlockedPanel
      endpoint="POST/GET /api/v1/batches, /api/v1/batches/{id}, /api/v1/batches/{id}/results"
      contractDoc="docs/API_CONTRACTS.md §1.2–§1.4"
    >
      Upload a JSONL/CSV/TXT file, watch progress, then stream per-question
      results. Typed request/response stubs are in{" "}
      <code>src/types/admin.ts</code>.
    </BlockedPanel>
  );
}
