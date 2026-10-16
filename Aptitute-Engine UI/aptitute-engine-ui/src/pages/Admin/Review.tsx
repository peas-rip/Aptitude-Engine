import { BlockedPanel } from "../../components/BlockedPanel";
import type { ReviewQueue } from "../../types/admin";

/**
 * Review queue — BLOCKED (spec §8.9).
 *
 * Intended flow: GET /api/v1/batches/{id}/review → list items with their
 * `reason_codes`, approve/reject inline. Stub type lives in src/types/admin.ts.
 */
export default function AdminReview() {
  void (0 as unknown as ReviewQueue);

  return (
    <BlockedPanel
      endpoint="GET /api/v1/batches/{batch_id}/review"
      contractDoc="docs/API_CONTRACTS.md §1.5"
    >
      Low-confidence and validation-failed questions awaiting a human decision.
      Typed response stub is in <code>src/types/admin.ts</code>.
    </BlockedPanel>
  );
}
