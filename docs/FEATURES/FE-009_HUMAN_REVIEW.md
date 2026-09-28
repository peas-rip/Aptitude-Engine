# Feature Specification: Human Review Workflow

## Business Goal
Flag uncertain or invalid questions for human review without blocking pipeline.

## User Flow
1. Validation pipeline produces ValidationResult
2. If status=needs_review: add to review queue with reason codes
3. Review queue exported as review.jsonl
4. Human reviews via CLI or future UI
5. Resolution: approve, edit, reject
6. Approved -> status=validated, re-export
7. Rejected -> status=failed, excluded from output

## Service Ownership
metadata-engine -> output/review_queue.py, api/routes/batches.py

## Database Requirements
- review_queue table (V2)
- V1: review.jsonl file

## API Requirements
- GET /api/v1/batches/{id}/review
- CLI: qme review --input review.jsonl --action approve|reject|edit

## Validation Requirements
- Reason codes from controlled vocabulary:
  - low_confidence (stage name)
  - validation_failed (layer name)
  - answer_mismatch
  - formula_unknown
  - taxonomy_ambiguous
- Priority: based on severity + volume

## Security Requirements
- Reviewer authentication (V2)
- Audit trail of review decisions

## Dependencies
- Requires: ValidationResult (FE-006)
- Provides: Clean output (validated only)

## Edge Cases
- Bulk review actions
- Disagreement between reviewers -> escalate
- Review modifies question -> new content_hash
- Review of reviewed -> versioned resolutions

## Error Handling
- Review queue corruption -> rebuild from validation logs
- Concurrent reviews -> last-write-wins with warning

## Acceptance Criteria
- Review queue exported with all flagged questions
- Reason codes actionable
- Resolution updates question status
- Audit trail complete

## Success Criteria
- Review throughput >50 questions/hour
- <5% questions need review on clean data
- Review decisions tracked
