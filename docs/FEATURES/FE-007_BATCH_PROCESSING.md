# Feature Specification: Batch Processing Pipeline

## Business Goal
Process thousands of questions reliably with checkpointing, retries, and cost tracking.

## User Flow
1. User submits batch file via API or CLI
2. BatchCoordinator creates processing run
3. Iterate questions sequentially:
   a) Load checkpoint (processed IDs)
   b) Skip already processed
   c) Run full pipeline per question
   d) Save checkpoint every N (default 10)
   e) On error: retry (3x exponential backoff)
   f) On permanent failure: log to failed.jsonl, continue
4. On completion: write output.jsonl, review.jsonl, metrics.json
5. Update processing run status

## Service Ownership
metadata-engine -> pipeline/coordinator.py, pipeline/checkpoint.py

## Database Requirements
- processing_runs table (V2)
- question_processing_log table (V2)
- V1: JSONL files + checkpoint files

## API Requirements
- POST /api/v1/batches (submit)
- GET /api/v1/batches/{id} (status)
- GET /api/v1/batches/{id}/results (download)
- CLI: qme process --input --output --checkpoint-dir

## Validation Requirements
- Checkpoint atomic writes (temp file + rename)
- Resume validates checkpoint integrity
- Rate limiting: token bucket per model
- Cost tracking: accumulate tokens, estimate USD

## Security Requirements
- Input file validation before processing
- Checkpoint files not world-readable

## Dependencies
- Requires: All pipeline stages (FE-001 through FE-006)
- Provides: Batch outputs, metrics, run metadata

## Edge Cases
- Interrupt (SIGTERM) -> save checkpoint, exit cleanly
- OOM -> checkpoint survives, resume works
- Partial output -> resume continues from last checkpoint
- Rate limit 429 -> wait, retry, continue
- Model API changes -> versioned prompts protect

## Error Handling
- Per-question: retry 3x, then failed.jsonl
- Batch-level: aggregate stats, never crash entire batch
- Checkpoint corruption: detect, backup, restart from last good

## Acceptance Criteria
- Process 1000 questions end-to-end
- Kill at 500 -> resume processes 501-1000 only
- Rate limits respected (no 429 errors)
- Cost tracking within 10% of actual
- Output files valid JSONL

## Success Criteria
- 10K questions in <8 hours (sequential)
- Zero data loss on interrupt
- Cost visibility per batch
