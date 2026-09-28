# Feature Specification: Source Tracking & Versioning

## Business Goal
Full provenance for every question: trace back to original source, processing version, model, prompt.

## User Flow
1. At ingestion: capture source metadata (name, type, identifier, page, question_id)
2. At each pipeline stage: record model, prompt version, tokens, duration
3. At output: assemble complete processing_metadata
4. Content hash (SHA256) computed for deduplication
5. All versions recorded: schema, taxonomy, prompts, models, methodology

## Service Ownership
metadata-engine -> ingestion/source_tracker.py, core/models.py

## Database Requirements
- questions table: all provenance fields
- prompts table (versioned)
- processing_runs table (config snapshot)

## API Requirements
- Input: source object in request
- Output: All provenance fields in EnrichedQuestion
- Config: processing_version (semver), methodology_version

## Validation Requirements
- content_hash: SHA256 of normalized question_text + options + answer
- All provenance fields non-empty (except optional page)
- processing_version matches deployed version
- prompt_version is hash of prompt template

## Security Requirements
- No PII in provenance (assume clean sources)
- Source identifiers sanitized

## Dependencies
- All stages: each adds processing metadata
- Provides: Complete audit trail

## Edge Cases
- Manual input (no source) -> source_type=manual, identifier=uuid
- Re-processing -> new question_id, previous versions in log
- Multiple sources for same question -> primary + references

## Error Handling
- Missing source fields -> warn, use defaults
- Hash computation failure -> log, continue

## Acceptance Criteria
- Every output question has complete provenance
- Content hash deterministic (same input = same hash)
- Re-processing creates new record with lineage
- Prompt hash enables exact reproduction

## Success Criteria
- 100% provenance completeness
- Deduplication engine can use content_hash
- Audit trail queryable
