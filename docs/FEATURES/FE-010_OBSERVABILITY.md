# Feature Specification: Observability & Cost Tracking

## Business Goal
Visibility into processing: metrics, logs, costs, performance.

## User Flow
1. Every LLM call: record tokens, model, latency, cost
2. Every pipeline stage: record duration, status
3. Batch level: aggregate throughput, success rates, cost
4. Export: Prometheus metrics, JSON logs, batch metrics.json
5. Alerting on thresholds (V2)

## Service Ownership
metadata-engine -> llm/cost_tracker.py, output/metrics_collector.py, api/routes/metrics.py

## Database Requirements
- processing_runs: total_tokens, estimated_cost
- question_processing_log: per-question tokens, duration

## API Requirements
- GET /api/v1/metrics (Prometheus format)
- GET /api/v1/batches/{id} (includes cost)
- Batch metrics.json output

## Validation Requirements
- Token counts match OpenAI response
- Cost calculation uses current pricing
- Metrics latency <100ms

## Security Requirements
- No sensitive data in metrics/logs
- API keys never logged

## Dependencies
- All stages: emit metrics
- Provides: Operational visibility

## Edge Cases
- Streaming token counts (approximate until complete)
- Batch API pricing (50% discount)
- Model pricing changes -> versioned pricing config

## Error Handling
- Metrics emission failure -> log, don't block pipeline
- Cost calculation error -> estimate, flag

## Acceptance Criteria
- Per-question cost in output
- Batch metrics.json with totals
- Prometheus /metrics endpoint works
- Structured logs with correlation IDs

## Success Criteria
- Cost prediction within 10%
- Zero metric cardinality explosion
- Debugging via logs <5 min
