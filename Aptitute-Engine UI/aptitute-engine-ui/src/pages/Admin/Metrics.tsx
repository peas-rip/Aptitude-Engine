import { BlockedPanel } from "../../components/BlockedPanel";
import type { Metrics } from "../../types/admin";

/**
 * Cost & metrics — BLOCKED (spec §8.9).
 *
 * `GET /api/v1/metrics` is named in §1.6 but is not implemented, and no
 * response body is specified yet. Stub type lives in src/types/admin.ts.
 */
export default function AdminMetrics() {
  void (0 as unknown as Metrics);

  return (
    <BlockedPanel
      endpoint="GET /api/v1/metrics"
      contractDoc="docs/API_CONTRACTS.md §1.6"
    >
      Token usage, estimated cost and failure rate for the pipeline. Typed stub
      is in <code>src/types/admin.ts</code>.
    </BlockedPanel>
  );
}
