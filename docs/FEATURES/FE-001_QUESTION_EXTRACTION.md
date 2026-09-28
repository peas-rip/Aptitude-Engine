# Feature Specification: Question Extraction & Normalization

## Business Goal
Convert raw questions from multiple input formats into a standardized NormalizedQuestion object with clean text, validated options, and correct answer.

## User Flow
1. User provides input file (JSONL, CSV, TXT) or single question via API
2. System detects format and parses accordingly
3. Text normalized (whitespace, encoding, special chars)
4. Options standardized (A/B/C/D keys, trimmed)
5. Answer validated (exists in options, correct format)
6. Provenance metadata attached
7. Output: NormalizedQuestion ready for pipeline

## Service Ownership
metadata-engine -> ingestion module

## Database Requirements
None for V1 (file output). V2: questions table stores normalized fields.

## API Requirements
- POST /api/v1/questions/process (single)
- POST /api/v1/batches (file upload)
- CLI: qme ingest --input file --output dir

## Validation Requirements
- Required fields: question_text, options, correct_answer
- Options must be dict with keys A-D (or subset)
- correct_answer must match option key or be numeric
- Question text non-empty, reasonable length (<10KB)
- Encoding: UTF-8, reject invalid

## Security Requirements
- File size limit: 10MB
- MIME type validation (allowlist)
- Sanitize text for prompt injection (escape braces, limit length)
- No code execution from input

## Dependencies
- None (first pipeline stage)

## Edge Cases
- Missing options (numeric entry questions)
- Multiple correct answers (multi-select)
- Malformed JSONL lines (skip + log)
- CSV with/without headers
- TXT with custom delimiters
- PDF/DOCX: deferred to FE-009

## Error Handling
- Per-question errors: log, skip, continue batch
- Format detection failure: try all parsers, then fail
- Invalid answer: mark failed, include in failed.jsonl

## Acceptance Criteria
- Parse sample.jsonl (100 questions) -> 100 NormalizedQuestion
- Malformed lines skipped with error logged
- Output matches Pydantic NormalizedQuestion schema
- Provenance fields populated

## Success Criteria
- >99.9% parse success on clean data
- <1% false positive format detection
- Zero silent data corruption
