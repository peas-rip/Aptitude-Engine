# Feature Specification: Multi-Layer Validation

## Business Goal
Ensure output quality through 7 validation layers; never silently accept bad data.

## User Flow
1. Receive fully assembled EnrichedQuestion
2. Run 7 validation layers in sequence:
   a) Schema: Pydantic model compliance
   b) Answer: Option matching, type correctness
   c) Calculation: Verify math (V1: LLM, V2: SymPy)
   d) Formula Consistency: Formulas match solution steps
   e) Solution-Answer: Solution derives correct answer
   f) Metadata Consistency: Topic aligns with concepts, difficulty matches steps
   g) Confidence: All stage confidences >= thresholds
3. Aggregate results -> ValidationResult (validated/needs_review/failed)
4. Flag items for review queue with reason codes

## Service Ownership
metadata-engine -> validation/ module

## Database Requirements
- questions table: validation_status, validation_errors, validation_warnings
- review_queue table

## API Requirements
- Internal: Validator protocol
- Config: confidence_thresholds per stage
- Output: ValidationResult with issues array

## Validation Requirements
- Layer 1 (Schema): Pydantic validation error -> failed
- Layer 2 (Answer): correct_answer in options keys -> error if not
- Layer 3 (Calculation): V1: LLM verification; V2: SymPy exact
- Layer 4 (Formula): Every step formula_ref in formulas_used
- Layer 5 (Solution->Answer): Solution final_answer == correct_answer
- Layer 6 (Metadata): Topic concepts subset of classification concepts; difficulty factors consistent
- Layer 7 (Confidence): All stage confidences >= configured thresholds

## Security Requirements
- No code execution from validation (V1 LLM, V2 SymPy sandboxed)

## Dependencies
- Requires: Complete EnrichedQuestion
- Provides: ValidationResult, review queue items

## Edge Cases
- Numeric answer questions (no options) -> validate type/range
- Multi-select -> validate all correct answers present
- Approximate answers -> tolerance config
- Missing optional fields -> warnings not errors

## Error Handling
- Validation errors -> status=failed (schema) or needs_review (others)
- All issues logged with field, code, message
- Never silently drop questions

## Acceptance Criteria
- Zero silent failures on test suite
- Known bad inputs caught at appropriate layer
- Review queue populated with actionable reason codes
- Validation latency <2s per question

## Success Criteria
- Production validation failure rate <1%
- Review queue actionable (clear reason codes)
- Regression tests catch validation regressions
